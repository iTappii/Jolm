"""Chat events over Postgres LISTEN/NOTIFY (Ш-64).

A background live-route pass (`live_bg`) may run on any worker, while the client's
`GET /v1/chats/{id}/events` stream sits on another one. So the pass announces itself with
`NOTIFY chat_events, '<json>'` and every worker fans the notification out to its own SSE clients.

The payload is tiny (`{"chat": "<uuid>", "kind": "..."}`; Postgres allows 8000 bytes), the route
itself is never in it: a subscriber re-reads the stored live route when it is told to.

Kinds: `building` (a pass started), `live_route` (a pass ended well; the stored route is new),
`failed` (a pass failed; the stored route is unchanged), `resync` (internal: the listening
connection was re-established, so something may have been missed; re-read everything).

One `ChatEventBus` per process owns ONE dedicated listening connection for all subscribers; it is
started on the first subscription and reconnects with a growing pause when the connection drops.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional, Set
from uuid import UUID

import psycopg

log = logging.getLogger(__name__)

CHANNEL = "chat_events"
KINDS = ("building", "live_route", "failed")
QUEUE_SIZE = 32
CONNECT_WAIT_SEC = 5.0
RECONNECT_MIN_SEC = 0.5
RECONNECT_MAX_SEC = 15.0


async def publish(db: Any, chat_id: UUID, kind: str) -> None:
    """NOTIFY the chat's subscribers. Never raises: a missed notification only means a client
    sees the change a little later (on its next reconnect)."""
    payload = json.dumps({"chat": str(chat_id), "kind": kind})
    try:
        async with db.transaction() as conn:
            await conn.execute("SELECT pg_notify(%s, %s)", (CHANNEL, payload))
    except Exception:
        log.exception("could not publish a chat event")


class ChatEventBus:
    def __init__(self, conninfo: Optional[str] = None) -> None:
        self.conninfo = conninfo  # None: the configured DATABASE_URL (looked up on first use)
        self._subs: Dict[UUID, Set["asyncio.Queue[str]"]] = {}
        self._task: Optional["asyncio.Task[None]"] = None
        self._listening = asyncio.Event()

    def _url(self) -> str:
        if self.conninfo:
            return self.conninfo
        from app.config import get_settings

        return get_settings().database_url

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._listening.clear()
            self._task = asyncio.ensure_future(self._run())

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._listening.clear()

    @asynccontextmanager
    async def subscribe(self, chat_id: UUID) -> AsyncIterator["asyncio.Queue[str]"]:
        """Queue of event kinds for one chat. Registered BEFORE the caller reads its snapshot,
        so nothing that happens in between is lost (a repeat just re-reads the same state)."""
        queue: "asyncio.Queue[str]" = asyncio.Queue(QUEUE_SIZE)
        self._subs.setdefault(chat_id, set()).add(queue)
        try:
            await self.start()
            try:
                await asyncio.wait_for(self._listening.wait(), CONNECT_WAIT_SEC)
            except asyncio.TimeoutError:
                log.warning("chat events: LISTEN connection is not up yet; serving anyway")
            yield queue
        finally:
            subs = self._subs.get(chat_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    del self._subs[chat_id]

    def _put(self, queue: "asyncio.Queue[str]", kind: str) -> None:
        try:
            queue.put_nowait(kind)
        except asyncio.QueueFull:  # a slow client: collapse its backlog into one full re-read
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait("live_route")

    def _dispatch(self, payload: str) -> None:
        try:
            data = json.loads(payload)
            chat_id, kind = UUID(data["chat"]), data["kind"]
        except (ValueError, KeyError, TypeError):
            log.warning("chat events: ignoring a malformed notification")
            return
        if kind not in KINDS:
            return
        for queue in list(self._subs.get(chat_id, ())):
            self._put(queue, kind)

    def _resync_all(self) -> None:
        for queues in list(self._subs.values()):
            for queue in list(queues):
                self._put(queue, "resync")

    async def _run(self) -> None:
        pause = RECONNECT_MIN_SEC
        first = True
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(
                    self._url(), autocommit=True
                ) as conn:
                    await conn.execute("LISTEN %s" % CHANNEL)  # constant identifier, no user data
                    pause = RECONNECT_MIN_SEC
                    if not first:  # events may have been missed while we were away
                        self._resync_all()
                    first = False
                    self._listening.set()
                    async for note in conn.notifies():
                        self._dispatch(note.payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("chat events: the LISTEN connection failed")
            self._listening.clear()
            await asyncio.sleep(pause)
            pause = min(pause * 2, RECONNECT_MAX_SEC)
