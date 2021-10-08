import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()
logger = logging.getLogger(__name__)

ASCII_ART = (
    "   ________          __  _    __           __            ___    ____\n"
    "  / ____/ /_  ____ _/ /_| |  / /__  ____  / /_____  ____/   |  /  _/\n"
    " / /   / __ \\/ __ `/ __/| | / / _ \\/ __ \\/ __/ __ \\/ ___/ /| |  / /\n"
    "/ /___/ / / / /_/ / /_  | |/ /  __/ / / / /_/ /_/ / /  / ___ |_/ /\n"
    "\\____/_/ /_/\\__,_/\\__/  |___/\\___/_/ /_/\\__/\\____/_/  /_/  |_/___/\n"
    "                                                                    \n"
    "\n"
    "ChatVector AI Backend is Live!\n"
)

links_html = (
    '<p>'
    '<a href="/docs">API Docs</a> | '
    '<a href="/status">System Status</a>'
    '</p>'
)

def _is_browser(request: Request) -> bool:
    # Prefer Accept header, then fall back to User-Agent heuristics.
    accept = request.headers.get("accept", "").lower()
    if "application/json" in accept and "text/html" not in accept:
        return False
    if "text/html" in accept:
        return True
    user_agent = request.headers.get("user-agent", "").lower()
    return any(token in user_agent for token in ("mozilla", "chrome", "safari", "firefox", "edge"))


@router.get("/")
def root(request: Request):
    logger.info("Root endpoint accessed")
    if _is_browser(request):
        return HTMLResponse(content=f"<pre style=\"font-family: monospace;\">{ASCII_ART}</pre>{links_html}")
    return {"message": "ChatVector AI Backend is Live!"}
