"""Tiny Prometheus-format metrics without a dependency (Ш-51).

Per-process counters (each API process is scraped on its own; Prometheus sums them). They reset
on restart, which `rate()` handles. Labels are bounded: the route TEMPLATE (never the raw path),
the method and the status. DB gauges (job queue) are added by `GET /metrics` at scrape time.
"""

import threading
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
_lock = threading.Lock()
_requests: Dict[Tuple[str, str, int], int] = defaultdict(int)
_duration_sum: Dict[str, float] = defaultdict(float)
_duration_count: Dict[str, int] = defaultdict(int)
_buckets: Dict[Tuple[str, float], int] = defaultdict(int)
_llm_thresholds: Dict[int, int] = defaultdict(int)  # Ш-66: global token budget crossings
_llm_truncated = 0  # Ш-66: model replies cut by the output cap


def count_llm_budget_threshold(percent: int) -> None:
    with _lock:
        _llm_thresholds[percent] += 1


def count_llm_truncated() -> None:
    global _llm_truncated
    with _lock:
        _llm_truncated += 1


def observe_request(method: str, route: str, status: int, seconds: float) -> None:
    with _lock:
        _requests[(method, route, status)] += 1
        _duration_sum[route] += seconds
        _duration_count[route] += 1
        for bound in BUCKETS:
            if seconds <= bound:
                _buckets[(route, bound)] += 1


def reset() -> None:  # tests
    with _lock:
        _requests.clear()
        _duration_sum.clear()
        _duration_count.clear()
        _buckets.clear()
        _llm_thresholds.clear()
        global _llm_truncated
        _llm_truncated = 0


def _esc(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render(extra_gauges: Iterable[Tuple[str, str, float]] = ()) -> str:
    lines: List[str] = []
    with _lock:
        lines.append("# TYPE jol_http_requests_total counter")
        for (method, route, status), n in sorted(_requests.items()):
            lines.append(
                'jol_http_requests_total{method="%s",route="%s",status="%d"} %d'
                % (_esc(method), _esc(route), status, n)
            )
        lines.append("# TYPE jol_http_request_duration_seconds histogram")
        for route in sorted(_duration_count):
            for bound in BUCKETS:
                lines.append(
                    'jol_http_request_duration_seconds_bucket{route="%s",le="%s"} %d'
                    % (_esc(route), bound, _buckets[(route, bound)])
                )
            lines.append(
                'jol_http_request_duration_seconds_bucket{route="%s",le="+Inf"} %d'
                % (_esc(route), _duration_count[route])
            )
            lines.append(
                'jol_http_request_duration_seconds_sum{route="%s"} %.6f'
                % (_esc(route), _duration_sum[route])
            )
            lines.append(
                'jol_http_request_duration_seconds_count{route="%s"} %d'
                % (_esc(route), _duration_count[route])
            )
        lines.append("# TYPE jol_llm_budget_threshold_total counter")
        for percent, n in sorted(_llm_thresholds.items()):
            lines.append('jol_llm_budget_threshold_total{percent="%d"} %d' % (percent, n))
        lines.append("# TYPE jol_llm_truncated_total counter")
        lines.append("jol_llm_truncated_total %d" % _llm_truncated)
    for name, help_text, value in extra_gauges:
        lines.append("# HELP %s %s" % (name, help_text))
        lines.append("# TYPE %s gauge" % name)
        lines.append("%s %s" % (name, value))
    return "\n".join(lines) + "\n"
