"""In-process sliding-window rate limiter.

Guest chat must not write to the database (SSOT §3.1, Ш-30), so counters live in memory.
TODO(multi-instance): with several API processes every process counts on its own, so the real
limit is limit x processes; move to a shared store (Redis or a counters table) when scaling out.
State is lost on restart, which is acceptable for abuse protection.
"""

import time
from collections import deque
from typing import Callable, Deque, Dict, Iterable, Optional, Tuple


class SlidingWindowLimiter:
    def __init__(
        self,
        limit: int,
        window_sec: float,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 50_000,
    ) -> None:
        self.limit = limit
        self.window_sec = window_sec
        self.clock = clock
        self.max_keys = max_keys
        self._hits: Dict[str, Deque[float]] = {}

    def _fresh(self, key: str, now: float) -> Deque[float]:
        hits = self._hits.get(key)
        if hits is None:
            return deque()
        while hits and hits[0] <= now - self.window_sec:
            hits.popleft()
        return hits

    def retry_after(self, key: str) -> int:
        """0 when a request is allowed now, else whole seconds until the oldest hit expires."""
        now = self.clock()
        hits = self._fresh(key, now)
        if len(hits) < self.limit:
            return 0
        return max(1, int(hits[0] + self.window_sec - now) + 1)

    def record(self, key: str) -> None:
        now = self.clock()
        hits = self._fresh(key, now)
        hits.append(now)
        self._hits[key] = hits
        if len(self._hits) > self.max_keys:
            self._prune(now)

    def _prune(self, now: float) -> None:
        for key in [k for k in self._hits if not self._fresh(k, now)]:
            del self._hits[key]
        if len(self._hits) > self.max_keys:  # still too many live keys: drop the oldest ones
            oldest = sorted(self._hits, key=lambda k: self._hits[k][-1])
            for key in oldest[: len(self._hits) - self.max_keys]:
                del self._hits[key]


def acquire(checks: Iterable[Tuple[SlidingWindowLimiter, str]]) -> Optional[int]:
    """Count one request against every (limiter, key); nothing is counted if any is full.

    Returns None when allowed, else the Retry-After seconds.
    """
    checks = list(checks)
    wait = max((limiter.retry_after(key) for limiter, key in checks), default=0)
    if wait:
        return wait
    for limiter, key in checks:
        limiter.record(key)
    return None
