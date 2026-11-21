"""Guest chat (Ш-30): `POST /v1/chat/guest`, SSE. Stateless: nothing is written to the database.

Body: `{"messages": [{"role": "user"|"assistant", "content": "..."}], "locale": "ru"|"en"}`.
The client holds the history and sends it with every request.

Events (`event: <name>` + `data: <json>`):
- `text_delta`  `{"text": "..."}`
- `map_places`  `{"reason": "search", "places": [{id, name, category, lat, lon}]}` after each
  search_places call that found something, so the map can show the places being discussed
- `done`        `{"usage": {"input_tokens": n, "output_tokens": n}}`
- `error`       `{"code": "...", "message": "..."}` (ends the stream; no `done` follows)
"""

from typing import List, Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from app.chat import tools
from app.chat.deps import client_ip, install_id, make_llm
from app.chat.engine import ToolOutcome, TurnRecord, run_turn
from app.chat.prompts import GUEST, load_prompt
from app.chat.ratelimit import acquire
from app.chat.sse import format_event, sse_response
from app.errors import AppError
from app.i18n import pick_locale
from app.providers.llm import Message, ToolArgsError, ToolCall, parse_tool_args

router = APIRouter(prefix="/v1/chat", tags=["chat"])

MAX_MESSAGES = 20
MAX_MESSAGE_CHARS = 2000
MAX_TOTAL_CHARS = 8000
MAX_TOOL_ROUNDS = 3


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class GuestChatRequest(BaseModel):
    messages: List[ChatTurn] = Field(min_length=1, max_length=MAX_MESSAGES)
    locale: Optional[Literal["ru", "en"]] = None

    @model_validator(mode="after")
    def _limits(self):
        if self.messages[-1].role != "user":
            raise ValueError("the last message must be from the user")
        if sum(len(m.content) for m in self.messages) > MAX_TOTAL_CHARS:
            raise ValueError("history is too long")
        return self


@router.post("/guest")
async def guest_chat(payload: GuestChatRequest, request: Request):
    locale = payload.locale or pick_locale(request.headers.get("accept-language"))
    llm = make_llm(request)  # 503 before anything is counted
    limiters = request.app.state.chat_limiters
    checks = [(limiters.guest_ip, "ip:" + client_ip(request))]
    installation = install_id(request)
    if installation:
        checks.append((limiters.guest_install, "install:" + installation))
    wait = acquire(checks)
    if wait is not None:
        raise AppError(429, "rate_limited", headers={"Retry-After": str(wait)})

    db = request.app.state.db
    system = load_prompt(GUEST, locale).render()
    messages = [Message(role=m.role, content=m.content) for m in payload.messages]

    async def handle_tool(call: ToolCall) -> ToolOutcome:
        if call.name != tools.SEARCH_PLACES:
            return ToolOutcome({"error": "unknown tool %r" % call.name}, ok=False, error="unknown")
        try:
            args = parse_tool_args(call, tools.SearchPlacesArgs)
        except ToolArgsError as exc:
            return ToolOutcome({"error": str(exc)}, ok=False, error=str(exc))
        result, pins = await tools.search_places(db, args, locale)
        events = [("map_places", {"reason": "search", "places": pins})] if pins else []
        return ToolOutcome(result, events)

    async def frames():
        record = TurnRecord()
        turn = run_turn(
            llm,
            messages,
            [tools.SEARCH_PLACES_SPEC],
            system,
            handle_tool,
            record,
            locale,
            MAX_TOOL_ROUNDS,
        )
        try:
            async for name, data in turn:
                yield format_event(name, data)
        finally:
            await turn.aclose()
        if record.error is None:
            usage = {
                "input_tokens": record.usage.input_tokens,
                "output_tokens": record.usage.output_tokens,
            }
            yield format_event("done", {"usage": usage})

    return sse_response(frames())
