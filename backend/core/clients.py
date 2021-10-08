from redis.asyncio import Redis
from core.config import config, redis_connection_kwargs
from utils.url_display import safe_url_display
import logging

logger = logging.getLogger(__name__)


class _LazyRedisClient:
    """Lazy-initializing Redis client proxy."""
    def __init__(self):
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            self._client = Redis.from_url(
                config.REDIS_URL,
                decode_responses=True,
                **redis_connection_kwargs(),
            )
            logger.info(
                "Redis client initialized at %s",
                safe_url_display(config.REDIS_URL),
            )

    def __getattr__(self, name):
        self._ensure_client()
        return getattr(self._client, name)


redis_client = _LazyRedisClient()
