"""Server-Sent Events framing for chat streams."""

import json
from typing import Any, AsyncIterator, Dict

from fastapi.responses import StreamingResponse


def format_event(name: str, data: Dict[str, Any]) -> str:
    """`event: <name>\\ndata: <json>\\n\\n`; JSON is one line, so one `data:` line is enough."""
    return "event: %s\ndata: %s\n\n" % (name, json.dumps(data, ensure_ascii=False, default=str))


def sse_response(frames: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        frames,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
