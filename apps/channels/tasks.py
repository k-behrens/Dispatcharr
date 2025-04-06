# apps/channels/tasks.py
import logging
import os
import re
import requests
import time
import gc
from datetime import datetime

from celery import shared_task
from rapidfuzz import fuzz
from django.conf import settings
from django.db import transaction
from django.utils.text import slugify

from apps.channels.models import Channel
from apps.epg.models import EPGData, EPGSource
from core.models import CoreSettings

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.utils import SentenceTransformer

logger = logging.getLogger(__name__)

# Thresholds
BEST_FUZZY_THRESHOLD = 85
LOWER_FUZZY_THRESHOLD = 40
EMBED_SIM_THRESHOLD = 0.65

# Words we remove to help with fuzzy + embedding matching
COMMON_EXTRANEOUS_WORDS = [
    "tv", "channel", "network", "television",
    "east", "west", "hd", "uhd", "24/7",
    "1080p", "720p", "540p", "480p",
    "film", "movie", "movies"
]

def normalize_name(name: str) -> str:
    """
    A more aggressive normalization that:
      - Lowercases
      - Removes bracketed/parenthesized text
      - Removes punctuation
      - Strips extraneous words
      - Collapses extra spaces
    """
    if not name:
        return ""

    norm = name.lower()
    norm = re.sub(r"\[.*?\]", "", norm)
    norm = re.sub(r"\(.*?\)", "", norm)
    norm = re.sub(r"[^\w\s]", "", norm)
    tokens = norm.split()
    tokens = [t for t in tokens if t not in COMMON_EXTRANEOUS_WORDS]
    norm = " ".join(tokens).strip()
    return norm

@shared_task
def match_epg_channels():
    """
    Goes through all Channels and tries to find a matching EPGData row by:
      1) If channel.tvg_id is valid in EPGData, skip.
      2) If channel has a tvg_id but not found in EPGData, attempt direct EPGData lookup.
      3) Otherwise, perform name-based fuzzy matching with optional region-based bonus.
      4) If a match is found, we set channel.tvg_id
      5) Summarize and log results.
    """
    from sentence_transformers import util

    logger.info("Starting EPG matching logic...")

    st_model = SentenceTransformer.get_model()

    # Attempt to retrieve a "preferred-region" if configured
    try:
        region_obj = CoreSettings.objects.get(key="preferred-region")
        region_code = region_obj.value.strip().lower()
    except CoreSettings.DoesNotExist:
        region_code = None

    # Gather EPGData rows so we can do fuzzy matching in memory
    all_epg = {e.id: e for e in EPGData.objects.all()}

    epg_rows = []
    for e in list(all_epg.values()):
        epg_rows.append({
            "epg_id": e.id,
            "tvg_id": e.tvg_id or "",
            "raw_name": e.name,
            "norm_name": normalize_name(e.name),
        })

    epg_embeddings = None
    if any(row["norm_name"] for row in epg_rows):
        epg_embeddings = st_model.encode(
            [row["norm_name"] for row in epg_rows],
            convert_to_tensor=True
        )

    matched_channels = []
    channels_to_update = []

    source = EPGSource.objects.filter(is_active=True).first()
    epg_file_path = getattr(source, 'file_path', None) if source else None

    with transaction.atomic():
        for chan in Channel.objects.all():
            # skip if channel already assigned an EPG
            if chan.epg_data:
                continue

            # If channel has a tvg_id that doesn't exist in EPGData, do direct check.
            # I don't THINK this should happen now that we assign EPG on channel creation.
            if chan.tvg_id:
                epg_match = EPGData.objects.filter(tvg_id=chan.tvg_id).first()
                if epg_match:
                    chan.epg_data = epg_match
                    logger.info(f"Channel {chan.id} '{chan.name}' => EPG found by tvg_id={chan.tvg_id}")
                    channels_to_update.append(chan)
                    continue

            # C) Perform name-based fuzzy matching
            fallback_name = chan.tvg_id.strip() if chan.tvg_id else chan.name
            norm_chan = normalize_name(fallback_name)
            if not norm_chan:
                logger.info(f"Channel {chan.id} '{chan.name}' => empty after normalization, skipping")
                continue

            best_score = 0
            best_epg = None
            for row in epg_rows:
                if not row["norm_name"]:
                    continue
                base_score = fuzz.ratio(norm_chan, row["norm_name"])
                bonus = 0
                # Region-based bonus/penalty
                combined_text = row["tvg_id"].lower() + " " + row["raw_name"].lower()
                dot_regions = re.findall(r'\.([a-z]{2})', combined_text)
                if region_code:
                    if dot_regions:
                        if region_code in dot_regions:
                            bonus = 30  # bigger bonus if .us or .ca matches
                        else:
                            bonus = -15
                    elif region_code in combined_text:
                        bonus = 15
                score = base_score + bonus

                logger.debug(
                    f"Channel {chan.id} '{fallback_name}' => EPG row {row['epg_id']}: "
                    f"raw_name='{row['raw_name']}', norm_name='{row['norm_name']}', "
                    f"combined_text='{combined_text}', dot_regions={dot_regions}, "
                    f"base_score={base_score}, bonus={bonus}, total_score={score}"
                )

                if score > best_score:
                    best_score = score
                    best_epg = row

            # If no best match was found, skip
            if not best_epg:
                logger.info(f"Channel {chan.id} '{fallback_name}' => no EPG match at all.")
                continue

            # If best_score is above BEST_FUZZY_THRESHOLD => direct accept
            if best_score >= BEST_FUZZY_THRESHOLD:
                chan.epg_data = all_epg[best_epg["epg_id"]]
                chan.save()

                matched_channels.append((chan.id, fallback_name, best_epg["tvg_id"]))
                logger.info(
                    f"Channel {chan.id} '{fallback_name}' => matched tvg_id={best_epg['tvg_id']} "
                    f"(score={best_score})"
                )

            # If best_score is in the “middle range,” do embedding check
            elif best_score >= LOWER_FUZZY_THRESHOLD and epg_embeddings is not None:
                chan_embedding = st_model.encode(norm_chan, convert_to_tensor=True)
                sim_scores = util.cos_sim(chan_embedding, epg_embeddings)[0]
                top_index = int(sim_scores.argmax())
                top_value = float(sim_scores[top_index])
                if top_value >= EMBED_SIM_THRESHOLD:
                    matched_epg = epg_rows[top_index]
                    chan.epg_data = all_epg[matched_epg["epg_id"]]
                    chan.save()

                    matched_channels.append((chan.id, fallback_name, matched_epg["tvg_id"]))
                    logger.info(
                        f"Channel {chan.id} '{fallback_name}' => matched EPG tvg_id={matched_epg['tvg_id']} "
                        f"(fuzzy={best_score}, cos-sim={top_value:.2f})"
                    )
                else:
                    logger.info(
                        f"Channel {chan.id} '{fallback_name}' => fuzzy={best_score}, "
                        f"cos-sim={top_value:.2f} < {EMBED_SIM_THRESHOLD}, skipping"
                    )
            else:
                logger.info(
                    f"Channel {chan.id} '{fallback_name}' => fuzzy={best_score} < "
                    f"{LOWER_FUZZY_THRESHOLD}, skipping"
                )

        if channels_to_update:
            Channel.objects.bulk_update(channels_to_update, ['epg_data'])

    total_matched = len(matched_channels)
    if total_matched:
        logger.info(f"Match Summary: {total_matched} channel(s) matched.")
        for (cid, cname, tvg) in matched_channels:
            logger.info(f"  - Channel ID={cid}, Name='{cname}' => tvg_id='{tvg}'")
    else:
        logger.info("No new channels were matched.")

    logger.info("Finished EPG matching logic.")

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'updates',
        {
            'type': 'update',
            "data": {"success": True, "type": "epg_match"}
        }
    )

    SentenceTransformer.clear()
    gc.collect()
    return f"Done. Matched {total_matched} channel(s)."

@shared_task
def run_recording(channel_id, start_time_str, end_time_str):
    channel = Channel.objects.get(id=channel_id)

    start_time = datetime.fromisoformat(start_time_str)
    end_time = datetime.fromisoformat(end_time_str)

    duration_seconds = int((end_time - start_time).total_seconds())
    filename = f'{slugify(channel.name)}-{start_time.strftime("%Y-%m-%d_%H-%M-%S")}.mp4'

    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        "updates",
        {
            "type": "update",
            "data": {"success": True, "type": "recording_started", "channel": channel.name}
        },
    )

    logger.info(f"Starting recording for channel {channel.name}")
    with requests.get(f"http://localhost:5656/proxy/ts/stream/{channel.uuid}", headers={
        'User-Agent': 'Dispatcharr-DVR',
    }, stream=True) as response:
        # Raise an exception for bad responses (4xx, 5xx)
        response.raise_for_status()

        # Open the file in write-binary mode
        with open(f"/data/recordings/{filename}", 'wb') as file:
            start_time = time.time()  # Start the timer
            for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                if time.time() - start_time > duration_seconds:
                    print(f"Timeout reached: {duration_seconds} seconds")
                    break
                # Write the chunk to the file
                file.write(chunk)

        async_to_sync(channel_layer.group_send)(
            "updates",
            {
                "type": "update",
                "data": {"success": True, "type": "recording_ended", "channel": channel.name}
            },
        )

        # After the loop, the file and response are closed automatically.
        logger.info(f"Finished recording for channel {channel.name}")
