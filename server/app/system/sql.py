HEALTH = "SELECT 1 AS ok"

# Job queue state for /metrics (Ш-51). A dead job = finished with an error after max attempts.
JOB_GAUGES = """
SELECT
    count(*) FILTER (WHERE done_at IS NULL)                                   AS pending,
    COALESCE(floor(extract(epoch FROM now() - min(run_at)
             FILTER (WHERE done_at IS NULL AND run_at < now() - interval '1 minute')))::int, 0)
                                                                              AS overdue,
    count(*) FILTER (WHERE done_at IS NOT NULL AND error IS NOT NULL)         AS dead
FROM jobs
"""
