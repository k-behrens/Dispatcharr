import json
import threading
import time
import random
import re
from django.http import StreamingHttpResponse, JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from apps.proxy.config import TSConfig as Config
from . import proxy_server
from .channel_status import ChannelStatus
from .stream_generator import create_stream_generator
from .utils import get_client_ip
from .redis_keys import RedisKeys
import logging
from apps.channels.models import Channel, Stream
from apps.m3u.models import M3UAccount, M3UAccountProfile
from core.models import UserAgent, CoreSettings, PROXY_PROFILE_NAME
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

# Configure logging properly
logger = logging.getLogger("ts_proxy")


@api_view(['GET'])
def stream_ts(request, channel_id):
    """Stream TS data to client with immediate response and keep-alive packets during initialization"""
    client_user_agent = None
    logger.info(f"Fetching channel ID {channel_id}")
    channel = get_object_or_404(Channel, uuid=channel_id)

    try:
        # Generate a unique client ID
        client_id = f"client_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        client_ip = get_client_ip(request)
        logger.info(f"[{client_id}] Requested stream for channel {channel_id}")

        # Extract client user agent early
        for header in ['HTTP_USER_AGENT', 'User-Agent', 'user-agent']:
            if header in request.META:
                client_user_agent = request.META[header]
                logger.debug(f"[{client_id}] Client connected with user agent: {client_user_agent}")
                break

        # Start initialization if needed
        channel_initializing = False
        if not proxy_server.check_if_channel_exists(channel_id):
            # Initialize the channel (but don't wait for completion)
            logger.info(f"[{client_id}] Starting channel {channel_id} initialization")

            # Get stream details from channel model
            stream_id, profile_id = channel.get_stream()
            if stream_id is None or profile_id is None:
                return JsonResponse({'error': 'Channel not available'}, status=404)

            # Load in necessary objects for the stream
            logger.info(f"Fetching stream ID {stream_id}")
            stream = get_object_or_404(Stream, pk=stream_id)
            logger.info(f"Fetching profile ID {profile_id}")
            profile = get_object_or_404(M3UAccountProfile, pk=profile_id)

            # Load in the user-agent for the STREAM connection (not client)
            m3u_account = M3UAccount.objects.get(id=profile.m3u_account.id)
            stream_user_agent = UserAgent.objects.get(id=m3u_account.user_agent.id).user_agent
            if stream_user_agent is None:
                stream_user_agent = UserAgent.objects.get(id=CoreSettings.get_default_user_agent_id())
                logger.debug(f"No user agent found for account, using default: {stream_user_agent}")
            else:
                logger.debug(f"User agent found for account: {stream_user_agent}")

            # Generate stream URL based on the selected profile
            input_url = stream.url
            logger.debug("Executing the following pattern replacement:")
            logger.debug(f"  search: {profile.search_pattern}")
            safe_replace_pattern = re.sub(r'\$(\d+)', r'\\\1', profile.replace_pattern)
            logger.debug(f"  replace: {profile.replace_pattern}")
            logger.debug(f"  safe replace: {safe_replace_pattern}")
            stream_url = re.sub(profile.search_pattern, safe_replace_pattern, input_url)
            logger.debug(f"Generated stream url: {stream_url}")

            # Generate transcode command if needed
            stream_profile = channel.get_stream_profile()
            if stream_profile.is_redirect():
                return HttpResponseRedirect(stream_url)

            # Need to check if profile is transcoded
            logger.debug(f"Using profile {stream_profile} for stream {stream_id}")
            if stream_profile.is_proxy() or stream_profile is None:
                transcode = False
            else:
                transcode = True

            # Initialize channel with the stream's user agent (not the client's)
            success = proxy_server.initialize_channel(stream_url, channel_id, stream_user_agent, transcode)
            if proxy_server.redis_client:
                metadata_key = RedisKeys.channel_metadata(channel_id)
                profile_value = str(stream_profile)
                proxy_server.redis_client.hset(metadata_key, "profile", profile_value)
            if not success:
                return JsonResponse({'error': 'Failed to initialize channel'}, status=500)

            # If we're the owner, wait for connection to establish
            if proxy_server.am_i_owner(channel_id):
                manager = proxy_server.stream_managers.get(channel_id)
                if manager:
                    wait_start = time.time()
                    while not manager.connected:
                        if time.time() - wait_start > Config.CONNECTION_TIMEOUT:
                            proxy_server.stop_channel(channel_id)
                            return JsonResponse({'error': 'Connection timeout'}, status=504)
                        if not manager.should_retry():
                            proxy_server.stop_channel(channel_id)
                            return JsonResponse({'error': 'Failed to connect'}, status=502)
                        time.sleep(0.1)

            logger.info(f"[{client_id}] Successfully initialized channel {channel_id}")
            channel_initializing = True
            logger.info(f"[{client_id}] Channel {channel_id} initialization started")

        # Register client - can do this regardless of initialization state
        # Create local resources if needed
        if channel_id not in proxy_server.stream_buffers or channel_id not in proxy_server.client_managers:
            logger.debug(f"[{client_id}] Channel {channel_id} exists in Redis but not initialized in this worker - initializing now")

            # Get URL from Redis metadata
            url = None
            stream_user_agent = None  # Initialize the variable

            if proxy_server.redis_client:
                metadata_key = RedisKeys.channel_metadata(channel_id)
                url_bytes = proxy_server.redis_client.hget(metadata_key, "url")
                ua_bytes = proxy_server.redis_client.hget(metadata_key, "user_agent")
                profile_bytes = proxy_server.redis_client.hget(metadata_key, "profile")

                if url_bytes:
                    url = url_bytes.decode('utf-8')
                if ua_bytes:
                    stream_user_agent = ua_bytes.decode('utf-8')
                # Extract transcode setting from Redis
                if profile_bytes:
                    profile_str = profile_bytes.decode('utf-8')
                    use_transcode = (profile_str == PROXY_PROFILE_NAME or profile_str == 'None')
                    logger.debug(f"Using profile '{profile_str}' for channel {channel_id}, transcode={use_transcode}")
                else:
                    # Default settings when profile not found in Redis
                    profile_str = 'None'  # Default profile name
                    use_transcode = False  # Default to direct streaming without transcoding
                    logger.debug(f"No profile found in Redis for channel {channel_id}, defaulting to transcode={use_transcode}")

            # Use client_user_agent as fallback if stream_user_agent is None
            success = proxy_server.initialize_channel(url, channel_id, stream_user_agent or client_user_agent, use_transcode)
            if not success:
                logger.error(f"[{client_id}] Failed to initialize channel {channel_id} locally")
                return JsonResponse({'error': 'Failed to initialize channel locally'}, status=500)

            logger.info(f"[{client_id}] Successfully initialized channel {channel_id} locally")

        # Register client
        buffer = proxy_server.stream_buffers[channel_id]
        client_manager = proxy_server.client_managers[channel_id]
        client_manager.add_client(client_id, client_ip, client_user_agent)
        logger.info(f"[{client_id}] Client registered with channel {channel_id}")

        # Create a stream generator for this client
        generate = create_stream_generator(
            channel_id, client_id, client_ip, client_user_agent, channel_initializing
        )

        # Return the StreamingHttpResponse from the main function
        response = StreamingHttpResponse(
            streaming_content=generate(),
            content_type='video/mp2t'
        )
        response['Cache-Control'] = 'no-cache'
        return response

    except Exception as e:
        logger.error(f"Error in stream_ts: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_stream(request, channel_id):
    """Change stream URL for existing channel with enhanced diagnostics"""
    try:
        data = json.loads(request.body)
        new_url = data.get('url')
        user_agent = data.get('user_agent')

        if not new_url:
            return JsonResponse({'error': 'No URL provided'}, status=400)

        logger.info(f"Attempting to change stream URL for channel {channel_id} to {new_url}")

        # Enhanced channel detection
        in_local_managers = channel_id in proxy_server.stream_managers
        in_local_buffers = channel_id in proxy_server.stream_buffers

        # First check Redis directly before using our wrapper method
        redis_keys = None
        if proxy_server.redis_client:
            try:
                redis_keys = proxy_server.redis_client.keys(f"ts_proxy:*:{channel_id}*")
                redis_keys = [k.decode('utf-8') for k in redis_keys] if redis_keys else []
            except Exception as e:
                logger.error(f"Error checking Redis keys: {e}")

        # Now use our standard check
        channel_exists = proxy_server.check_if_channel_exists(channel_id)

        # Log detailed diagnostics
        logger.info(f"Channel {channel_id} diagnostics: "
                   f"in_local_managers={in_local_managers}, "
                   f"in_local_buffers={in_local_buffers}, "
                   f"redis_keys_count={len(redis_keys) if redis_keys else 0}, "
                   f"channel_exists={channel_exists}")

        if not channel_exists:
            # If channel doesn't exist but we found Redis keys, force initialize it
            if redis_keys:
                logger.warning(f"Channel {channel_id} not detected by check_if_channel_exists but Redis keys exist. Forcing initialization.")
                proxy_server.initialize_channel(new_url, channel_id, user_agent)
            else:
                logger.error(f"Channel {channel_id} not found in any worker or Redis")
                return JsonResponse({
                    'error': 'Channel not found',
                    'diagnostics': {
                        'in_local_managers': in_local_managers,
                        'in_local_buffers': in_local_buffers,
                        'redis_keys': redis_keys,
                    }
                }, status=404)

        # Update metadata in Redis regardless of ownership - this ensures URL is updated
        # even if the owner worker is handling another request
        if proxy_server.redis_client:
            try:
                metadata_key = RedisKeys.channel_metadata(channel_id)

                # First check if the key exists and what type it is
                key_type = proxy_server.redis_client.type(metadata_key).decode('utf-8')
                logger.debug(f"Redis key {metadata_key} is of type: {key_type}")

                # Use the appropriate method based on the key type
                if key_type == 'hash':
                    proxy_server.redis_client.hset(metadata_key, "url", new_url)
                    if user_agent:
                        proxy_server.redis_client.hset(metadata_key, "user_agent", user_agent)
                elif key_type == 'none':  # Key doesn't exist yet
                    # Create new hash with all required fields
                    metadata = {"url": new_url}
                    if user_agent:
                        metadata["user_agent"] = user_agent
                    proxy_server.redis_client.hset(metadata_key, mapping=metadata)
                else:
                    # If key exists with wrong type, delete it and recreate
                    proxy_server.redis_client.delete(metadata_key)
                    metadata = {"url": new_url}
                    if user_agent:
                        metadata["user_agent"] = user_agent
                    proxy_server.redis_client.hset(metadata_key, mapping=metadata)

                # Set switch request flag to ensure all workers see it
                switch_key = RedisKeys.switch_request(channel_id)
                proxy_server.redis_client.setex(switch_key, 30, new_url)  # 30 second TTL

                logger.info(f"Updated metadata for channel {channel_id} in Redis")
            except Exception as e:
                logger.error(f"Error updating Redis metadata: {e}", exc_info=True)

        # If we're the owner, update directly
        if proxy_server.am_i_owner(channel_id) and channel_id in proxy_server.stream_managers:
            logger.info(f"This worker is the owner, changing stream URL for channel {channel_id}")
            manager = proxy_server.stream_managers[channel_id]
            old_url = manager.url

            # Update the stream
            result = manager.update_url(new_url)
            logger.info(f"Stream URL changed from {old_url} to {new_url}, result: {result}")
            return JsonResponse({
                'message': 'Stream URL updated',
                'channel': channel_id,
                'url': new_url,
                'owner': True,
                'worker_id': proxy_server.worker_id
            })

        # If we're not the owner, publish an event for the owner to pick up
        else:
            logger.info(f"This worker is not the owner, requesting URL change via Redis PubSub")
            # Publish switch request event
            switch_request = {
                "event": "stream_switch",
                "channel_id": channel_id,
                "url": new_url,
                "user_agent": user_agent,
                "requester": proxy_server.worker_id,
                "timestamp": time.time()
            }

            proxy_server.redis_client.publish(
                RedisKeys.events_channel(channel_id),
                json.dumps(switch_request)
            )

            return JsonResponse({
                'message': 'Stream URL change requested',
                'channel': channel_id,
                'url': new_url,
                'owner': False,
                'worker_id': proxy_server.worker_id
            })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Failed to change stream: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def channel_status(request, channel_id=None):
    """
    Returns status information about channels with detail level based on request:
    - /status/ returns basic summary of all channels
    - /status/{channel_id} returns detailed info about specific channel
    """
    try:
        # Check if Redis is available
        if not proxy_server.redis_client:
            return JsonResponse({'error': 'Redis connection not available'}, status=500)

        # Handle single channel or all channels
        if channel_id:
            # Detailed info for specific channel
            channel_info = ChannelStatus.get_detailed_channel_info(channel_id)
            if channel_info:
                return JsonResponse(channel_info)
            else:
                return JsonResponse({'error': f'Channel {channel_id} not found'}, status=404)
        else:
            # Basic info for all channels
            channel_pattern = "ts_proxy:channel:*:metadata"
            all_channels = []

            # Extract channel IDs from keys
            cursor = 0
            while True:
                cursor, keys = proxy_server.redis_client.scan(cursor, match=channel_pattern)
                for key in keys:
                    channel_id_match = re.search(r"ts_proxy:channel:(.*):metadata", key.decode('utf-8'))
                    if channel_id_match:
                        ch_id = channel_id_match.group(1)
                        channel_info = ChannelStatus.get_basic_channel_info(ch_id)
                        if channel_info:
                            all_channels.append(channel_info)

                if cursor == 0:
                    break

            return JsonResponse({'channels': all_channels, 'count': len(all_channels)})

    except Exception as e:
        logger.error(f"Error in channel_status: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def stop_channel(request, channel_id):
    """Stop a channel and release all associated resources using PubSub events"""
    try:
        logger.info(f"Request to stop channel {channel_id} received")

        # Check if channel exists
        channel_exists = proxy_server.check_if_channel_exists(channel_id)
        if not channel_exists:
            logger.warning(f"Channel {channel_id} not found in any worker or Redis")
            return JsonResponse({'error': 'Channel not found'}, status=404)

        # Get channel state information for response
        channel_info = None
        if proxy_server.redis_client:
            metadata_key = RedisKeys.channel_metadata(channel_id)
            try:
                metadata = proxy_server.redis_client.hgetall(metadata_key)
                if metadata and b'state' in metadata:
                    state = metadata[b'state'].decode('utf-8')
                    channel_info = {"state": state}
            except Exception as e:
                logger.error(f"Error fetching channel state: {e}")

        # Broadcast stop event to all workers via PubSub
        if proxy_server.redis_client:
            stop_request = {
                "event": "channel_stop",
                "channel_id": channel_id,
                "requester_worker_id": proxy_server.worker_id,
                "timestamp": time.time()
            }

            # Publish the stop event
            proxy_server.redis_client.publish(
                RedisKeys.events_channel(channel_id),
                json.dumps(stop_request)
            )

            logger.info(f"Published channel stop event for {channel_id}")

            # Also stop locally to ensure this worker cleans up right away
            result = proxy_server.stop_channel(channel_id)
        else:
            # No Redis, just stop locally
            result = proxy_server.stop_channel(channel_id)

        # Release the channel in the channel model if applicable
        try:
            channel = Channel.objects.get(uuid=channel_id)
            channel.release_stream()
            logger.info(f"Released channel {channel_id} stream allocation")
        except Channel.DoesNotExist:
            logger.warning(f"Could not find Channel model for UUID {channel_id}")
        except Exception as e:
            logger.error(f"Error releasing channel stream: {e}")

        return JsonResponse({
            'message': 'Channel stop request sent',
            'channel_id': channel_id,
            'previous_state': channel_info
        })

    except Exception as e:
        logger.error(f"Failed to stop channel: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_client(request, channel_id):
    """Stop a specific client connection using existing client management"""
    try:
        # Parse request body to get client ID
        data = json.loads(request.body)
        client_id = data.get('client_id')

        if not client_id:
            return JsonResponse({'error': 'No client_id provided'}, status=400)

        logger.info(f"Request to stop client {client_id} on channel {channel_id}")

        # Set a Redis key for the generator to detect regardless of whether client is local
        if proxy_server.redis_client:
            stop_key = RedisKeys.client_stop(channel_id, client_id)
            proxy_server.redis_client.setex(stop_key, 30, "true")  # 30 second TTL
            logger.info(f"Set stop key for client {client_id}")

        # Check if channel exists
        channel_exists = proxy_server.check_if_channel_exists(channel_id)
        if not channel_exists:
            logger.warning(f"Channel {channel_id} not found")
            return JsonResponse({'error': 'Channel not found'}, status=404)

        # Two-part approach:
        # 1. Handle locally if client is on this worker
        # 2. Use events to inform other workers if needed

        local_client_stopped = False
        if channel_id in proxy_server.client_managers:
            client_manager = proxy_server.client_managers[channel_id]
            # Use the existing remove_client method directly
            with client_manager.lock:
                if client_id in client_manager.clients:
                    client_manager.remove_client(client_id)
                    local_client_stopped = True
                    logger.info(f"Client {client_id} stopped locally on channel {channel_id}")

        # If client wasn't found locally, broadcast stop event for other workers
        if not local_client_stopped and proxy_server.redis_client:
            stop_request = {
                "event": "client_stop",
                "channel_id": channel_id,
                "client_id": client_id,
                "requester_worker_id": proxy_server.worker_id,
                "timestamp": time.time()
            }

            proxy_server.redis_client.publish(
                RedisKeys.events_channel(channel_id),
                json.dumps(stop_request)
            )
            logger.info(f"Published stop request for client {client_id} on channel {channel_id}")

        return JsonResponse({
            'message': 'Client stop request processed',
            'channel_id': channel_id,
            'client_id': client_id,
            'locally_processed': local_client_stopped
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Failed to stop client: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)
