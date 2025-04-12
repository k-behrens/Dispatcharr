"""
Debug wrapper for the WSGI application.
This module initializes debugpy and then imports the actual application.
"""
import sys
import os
import time
import logging
import inspect

# Configure logging to output to both console and file
os.makedirs('/app/debugpy_logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/debugpy_logs/debug_wrapper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('debug_wrapper')

# Log system info
logger.info(f"Python version: {sys.version}")
logger.info(f"Current directory: {os.getcwd()}")
logger.info(f"Files in current directory: {os.listdir()}")
logger.info(f"Python path: {sys.path}")

# Default timeout in seconds
DEBUG_TIMEOUT = int(os.environ.get('DEBUG_TIMEOUT', '30'))
# Whether to wait for debugger to attach
WAIT_FOR_DEBUGGER = os.environ.get('WAIT_FOR_DEBUGGER', 'false').lower() == 'true'

logger.info(f"DEBUG_TIMEOUT: {DEBUG_TIMEOUT}")
logger.info(f"WAIT_FOR_DEBUGGER: {WAIT_FOR_DEBUGGER}")

try:
    import debugpy
    from debugpy import configure
    logger.info("Successfully imported debugpy")

    # Critical: Configure debugpy to use regular Python for the adapter, not uwsgi
    python_path = '/usr/local/bin/python3'
    if os.path.exists(python_path):
        logger.info(f"Setting debugpy adapter to use Python interpreter: {python_path}")
        debugpy.configure(python=python_path)
    else:
        logger.warning(f"Python path {python_path} not found. Using system default.")

    # Don't wait for connection, just set up the debugging session
    logger.info("Initializing debugpy on 0.0.0.0:5678...")
    try:
        # Use connect instead of listen to avoid the adapter process
        debugpy.listen(("0.0.0.0", 5678))
        logger.info("debugpy now listening on 0.0.0.0:5678")

        if WAIT_FOR_DEBUGGER:
            logger.info(f"Waiting for debugger to attach (timeout: {DEBUG_TIMEOUT}s)...")
            start_time = time.time()
            while not debugpy.is_client_connected() and (time.time() - start_time < DEBUG_TIMEOUT):
                time.sleep(1)
                logger.info("Waiting for debugger connection...")

            if debugpy.is_client_connected():
                logger.info("Debugger attached!")
            else:
                logger.info(f"Debugger not attached after {DEBUG_TIMEOUT}s, continuing anyway...")
    except Exception as e:
        logger.error(f"Error with debugpy.listen: {e}", exc_info=True)
        logger.info("Continuing without debugging...")

except ImportError:
    logger.error("debugpy not installed, continuing without debugging support")
except Exception as e:
    logger.error(f"Failed to initialize debugpy: {e}", exc_info=True)
    logger.info("Continuing without debugging support")

# Now import the actual WSGI application
logger.info("Loading WSGI application...")
try:
    from dispatcharr.wsgi import application
    logger.info("WSGI application loaded successfully")

    # Log the application details
    logger.info(f"Application type: {type(application)}")
    logger.info(f"Application callable: {inspect.isfunction(application) or inspect.ismethod(application)}")

except Exception as e:
    logger.error(f"Error loading WSGI application: {e}", exc_info=True)
    raise
