# apps/channels/tasks.py
import logging
import os
import re
import requests
import time
import json
import subprocess
from datetime import datetime

from celery import shared_task
from django.utils.text import slugify

from apps.channels.models import Channel
from apps.epg.models import EPGData
from core.models import CoreSettings

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import tempfile

logger = logging.getLogger(__name__)

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
    logger.info("Starting EPG matching logic...")

    # Attempt to retrieve a "preferred-region" if configured
    try:
        region_obj = CoreSettings.objects.get(key="preferred-region")
        region_code = region_obj.value.strip().lower()
    except CoreSettings.DoesNotExist:
        region_code = None

    matched_channels = []
    channels_to_update = []

    channels_json = [{
        "id": channel.id,
        "name": channel.name,
        "tvg_id": channel.tvg_id,
        "fallback_name": channel.tvg_id.strip() if channel.tvg_id else channel.name,
        "norm_chan": normalize_name(channel.tvg_id.strip() if channel.tvg_id else channel.name)
    } for channel in Channel.objects.all() if not channel.epg_data]

    epg_json = [{
        'id': epg.id,
        'tvg_id': epg.tvg_id,
        'name': epg.name,
        'norm_name': normalize_name(epg.name),
        'epg_source_id': epg.epg_source.id,
    } for epg in EPGData.objects.all()]

    payload = {
        "channels": channels_json,
        "epg_data": epg_json,
        "region_code": region_code,
    }

    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(json.dumps(payload).encode('utf-8'))
        temp_file_path = temp_file.name

    process = subprocess.Popen(
        ['python', '/app/scripts/epg_match.py', temp_file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Log stderr in real-time
    for line in iter(process.stderr.readline, ''):
        if line:
            logger.info(line.strip())

    process.stderr.close()
    stdout, stderr = process.communicate()

    os.remove(temp_file_path)

    if process.returncode != 0:
        return f"Failed to process EPG matching: {stderr}"

    result = json.loads(stdout)
    # This returns lists of dicts, not model objects
    channels_to_update_dicts = result["channels_to_update"]
    matched_channels = result["matched_channels"]

    # Convert your dict-based 'channels_to_update' into real Channel objects
    if channels_to_update_dicts:
        # Extract IDs of the channels that need updates
        channel_ids = [d["id"] for d in channels_to_update_dicts]

        # Fetch them from DB
        channels_qs = Channel.objects.filter(id__in=channel_ids)
        channels_list = list(channels_qs)

        # Build a map from channel_id -> epg_data_id (or whatever fields you need)
        epg_mapping = {
            d["id"]: d["epg_data_id"] for d in channels_to_update_dicts
        }

        # Populate each Channel object with the updated epg_data_id
        for channel_obj in channels_list:
            # The script sets 'epg_data_id' in the returned dict
            # We either assign directly, or fetch the EPGData instance if needed.
            channel_obj.epg_data_id = epg_mapping.get(channel_obj.id)

        # Now we have real model objects, so bulk_update will work
        Channel.objects.bulk_update(channels_list, ["epg_data"])

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
