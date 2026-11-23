"""Live route built in the background (Ш-64, SSOT §11.1 «Чат не ждёт карту»).

`update_trip_brief` used to wait for `live_route.sync` (place search + one router call per leg)
before the model could write its answer. Now it only SCHEDULES a pass here and returns at once:

- one pass runner per chat per process; a request that arrives while a pass runs does not start a
  second runner but marks the chat dirty, and exactly ONE more pass runs afterwards (latest wins);
- a pass reads the LATEST must-have wishes from the stored brief when it starts, never a captured
  list, and runs `live_route.sync` under `chat_lock` (serialised across workers and with `choose`);
- when a pass ends it announces it with Postgres NOTIFY (`events_bus`): `building` at the start,
  `live_route` on success, `failed` on failure (the stored route is then unchanged);
- it never holds the chat's turn lease: the user can send the next message right away.

`Ticket` lets the message stream peek, without waiting, whether the pass for its update already
ended (then the stream also carries `live_route` before `done`, like before Ш-64).
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from app.chat import events_bus, live_route, store

log = logging.getLogger(__name__)


@dataclass
class PassResult:
    ok: bool
    route: Optional[Dict[str, Any]] = None
    changed: bool = False
    pins: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # new wish -> best pin


class Ticket:
    """Result of the pass that covers one schedule() call; `result` is None until it ended."""

    def __init__(self) -> None:
        self.result: Optional[PassResult] = None


class _Job:
    def __init__(self, db: Any, chat_id: UUID, locale: str, router: Any) -> None:
        self.db, self.chat_id, self.locale, self.router = db, chat_id, locale, router
        self.dirty = False
        self.waiting: List[Ticket] = []  # asked for, not yet covered by a started pass
        self.idle = asyncio.Event()
        self.task: Optional["asyncio.Task[None]"] = None


class LiveRouteScheduler:
    """Per-process registry of live-route passes (kept on `app.state`)."""

    def __init__(self) -> None:
        self._jobs: Dict[UUID, _Job] = {}
        self._tasks: Set["asyncio.Task[None]"] = set()  # strong references until they finish
        self.passes = 0  # how many passes ran (tests and metrics)

    def is_building(self, chat_id: UUID) -> bool:
        return chat_id in self._jobs

    def schedule(self, db: Any, chat_id: UUID, locale: str, router: Any) -> Ticket:
        """Ask for a pass; returns at once. Synchronous on purpose: it cannot be interleaved
        with the runner's decision to stop, so a request is never lost."""
        ticket = Ticket()
        job = self._jobs.get(chat_id)
        if job is None:
            job = self._jobs[chat_id] = _Job(db, chat_id, locale, router)
            job.waiting.append(ticket)
            job.task = asyncio.ensure_future(self._run(job))
            self._tasks.add(job.task)
            job.task.add_done_callback(self._tasks.discard)
        else:
            job.dirty = True
            job.waiting.append(ticket)
            job.router = router
        return ticket

    async def wait_idle(self, chat_id: UUID) -> None:
        """Wait until no pass is pending for the chat (the trip builder needs the final stops)."""
        job = self._jobs.get(chat_id)
        if job is not None:
            await job.idle.wait()

    async def drain(self) -> None:
        """Wait for every pass to end (tests, graceful shutdown of a quiet server)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def close(self) -> None:
        """Application shutdown: cancel the passes cleanly. A cancelled pass rolls back its
        transaction; the stored route stays as it was and the next message schedules it again."""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _run(self, job: _Job) -> None:
        started = time.perf_counter()
        passes = 0
        tickets: List[Ticket] = []
        try:
            await events_bus.publish(job.db, job.chat_id, "building")
            while True:
                job.dirty = False
                tickets, job.waiting = (
                    job.waiting,
                    [],
                )  # read the brief AFTER this: they are covered
                result = await self._one_pass(job)
                passes += 1
                self.passes += 1
                if job.dirty:  # another request came in meanwhile: one more pass, latest wins;
                    job.waiting = tickets + job.waiting  # the tickets wait for that pass instead
                    continue
                for ticket in tickets:
                    ticket.result = result
                await events_bus.publish(
                    job.db, job.chat_id, "live_route" if result.ok else "failed"
                )
                break
        except asyncio.CancelledError:
            raise
        except Exception:  # _one_pass catches its own errors; this is the publish itself
            log.exception("live route runner failed")
        finally:
            for ticket in tickets + job.waiting:  # cancelled or crashed: nobody waits forever
                if ticket.result is None:
                    ticket.result = PassResult(ok=False)
            del self._jobs[job.chat_id]  # no await between the last dirty check and here
            job.idle.set()
            log.info(
                "live route runner",
                extra={
                    "total_ms": round((time.perf_counter() - started) * 1000),
                    "passes": passes,
                },
            )

    async def _one_pass(self, job: _Job) -> PassResult:
        started = time.perf_counter()
        try:
            async with job.db.transaction() as conn:
                brief = await store.get_brief(conn, job.chat_id)
            route, changed, pins = await live_route.sync(
                job.db, job.chat_id, job.locale, job.router, brief["must_haves"]
            )
            return PassResult(True, route, changed, pins)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("live route pass failed")
            return PassResult(ok=False)
        finally:
            log.info(
                "live route pass", extra={"sync_ms": round((time.perf_counter() - started) * 1000)}
            )


class TurnLive:
    """The scheduler as one chat turn sees it: schedule passes, peek at their tickets."""

    def __init__(
        self, scheduler: LiveRouteScheduler, db: Any, chat_id: UUID, locale: str, router: Any
    ) -> None:
        self.scheduler, self.db, self.chat_id = scheduler, db, chat_id
        self.locale, self.router = locale, router
        self.tickets: List[Ticket] = []

    def schedule(self) -> None:
        self.tickets.append(
            self.scheduler.schedule(self.db, self.chat_id, self.locale, self.router)
        )

    async def wait_idle(self) -> None:
        await self.scheduler.wait_idle(self.chat_id)

    def finished(self) -> Optional[PassResult]:
        """The result of the latest scheduled pass if it already ended (never waits)."""
        if self.tickets and self.tickets[-1].result is not None:
            return self.tickets[-1].result
        return None
