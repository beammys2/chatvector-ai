import logging
from middleware.request_id import get_request_id

class RequestIDFilter(logging.Filter):
    """Inject request_id into application log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "system"
        return True


