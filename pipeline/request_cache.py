"""
Shared HTTP request cache for enrichment APIs.

The cache avoids repeating identical GET requests across pipeline runs,
which matters for backfills and scheduled jobs that may revisit the same
event/date/station combinations.
"""

import logging

import requests_cache

from pipeline.config import CACHE_EXPIRATION, DATA_DIR, REQUEST_CACHE_NAME

logger = logging.getLogger(__name__)

_session = None


def get_cached_session():
    """Return a process-wide cached requests session."""
    global _session
    if _session is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _session = requests_cache.CachedSession(
            cache_name=str(REQUEST_CACHE_NAME),
            backend="sqlite",
            expire_after=CACHE_EXPIRATION,
            allowable_methods=("GET",),
            allowable_codes=(200,),
        )
        logger.info(f"HTTP request cache enabled at {REQUEST_CACHE_NAME}.sqlite")
    return _session
