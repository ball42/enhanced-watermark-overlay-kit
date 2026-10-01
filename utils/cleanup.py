"""
Periodic cleanup for temp and upload directories.
Removes files older than 1 hour, runs at most every 5 minutes.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)

_last_cleanup = 0
CLEANUP_INTERVAL = 300  # 5 minutes
MAX_FILE_AGE = 3600  # 1 hour


def cleanup_old_files(*directories):
    """Remove files older than MAX_FILE_AGE from the given directories."""
    global _last_cleanup
    now = time.time()

    if now - _last_cleanup < CLEANUP_INTERVAL:
        return

    _last_cleanup = now
    removed = 0

    for directory in directories:
        if not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                if now - os.path.getmtime(filepath) > MAX_FILE_AGE:
                    os.remove(filepath)
                    removed += 1
            except OSError:
                pass

    if removed:
        logger.info("Cleanup: removed %d old file(s)", removed)
