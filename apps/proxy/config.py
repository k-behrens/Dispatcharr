"""Shared configuration between proxy types"""

class BaseConfig:
    DEFAULT_USER_AGENT = 'VLC/3.0.20 LibVLC/3.0.20' # Will only be used if connection to settings fail
    CHUNK_SIZE = 8192
    CLIENT_POLL_INTERVAL = 0.1
    MAX_RETRIES = 3
    RETRY_WAIT_INTERVAL = 0.5  # seconds to wait between retries
    CONNECTION_TIMEOUT = 10  # seconds to wait for initial connection
    MAX_STREAM_SWITCHES = 10  # Maximum number of stream switch attempts before giving up
    BUFFER_CHUNK_SIZE = 188 * 1361  # ~256KB
    # Redis settings
    REDIS_CHUNK_TTL = 60  # Number in seconds - Chunks expire after 1 minute

class HLSConfig(BaseConfig):
    MIN_SEGMENTS = 12
    MAX_SEGMENTS = 16
    WINDOW_SIZE = 12
    INITIAL_SEGMENTS = 3
    INITIAL_CONNECTION_WINDOW = 10
    CLIENT_TIMEOUT_FACTOR = 1.5
    CLIENT_CLEANUP_INTERVAL = 10
    FIRST_SEGMENT_TIMEOUT = 5.0
    INITIAL_BUFFER_SECONDS = 25.0
    MAX_INITIAL_SEGMENTS = 10
    BUFFER_READY_TIMEOUT = 30.0

class TSConfig(BaseConfig):
    """Configuration settings for TS proxy"""

    # Buffer settings
    INITIAL_BEHIND_CHUNKS = 4  # How many chunks behind to start a client (4 chunks = ~1MB)
    CHUNK_BATCH_SIZE = 5       # How many chunks to fetch in one batch
    KEEPALIVE_INTERVAL = 0.5   # Seconds between keepalive packets when at buffer head

    # Streaming settings
    TARGET_BITRATE = 8000000   # Target bitrate (8 Mbps)
    STREAM_TIMEOUT = 10        # Disconnect after this many seconds of no data
    HEALTH_CHECK_INTERVAL = 5  # Check stream health every N seconds

    # Resource management
    CLEANUP_INTERVAL = 60  # Check for inactive channels every 60 seconds
    CHANNEL_SHUTDOWN_DELAY = 0  # How long to wait after last client before shutdown (seconds)

    # Client tracking settings
    CLIENT_RECORD_TTL = 5  # How long client records persist in Redis (seconds). Client will be considered MIA after this time.
    CLEANUP_CHECK_INTERVAL = 1  # How often to check for disconnected clients (seconds)
    CHANNEL_INIT_GRACE_PERIOD = 5  # How long to wait for first client after initialization (seconds)
    CLIENT_HEARTBEAT_INTERVAL = 1  # How often to send client heartbeats (seconds)
    GHOST_CLIENT_MULTIPLIER = 5.0  # How many heartbeat intervals before client considered ghost (5 would mean 5 secondsif heartbeat interval is 1)

    # TS packets are 188 bytes
    # Make chunk size a multiple of TS packet size for perfect alignment
    # ~1MB is ideal for streaming (matches typical media buffer sizes)

    # Stream health and recovery settings
    MAX_HEALTH_RECOVERY_ATTEMPTS = 2     # Maximum times to attempt recovery for a single stream
    MAX_RECONNECT_ATTEMPTS = 3           # Maximum reconnects to try before switching streams
    MIN_STABLE_TIME_BEFORE_RECONNECT = 30  # Minimum seconds a stream must be stable to try reconnect
    FAILOVER_GRACE_PERIOD = 20           # Extra time (seconds) to allow for stream switching before disconnecting clients




