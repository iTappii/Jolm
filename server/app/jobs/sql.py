CLAIM = """
SELECT id, kind, payload, attempts
FROM jobs
WHERE run_at <= now() AND done_at IS NULL
ORDER BY run_at
FOR UPDATE SKIP LOCKED
LIMIT %s
"""

MARK_CLAIMED = "UPDATE jobs SET locked_at = now() WHERE id = %s"

MARK_DONE = "UPDATE jobs SET done_at = now(), error = NULL WHERE id = %s"

# retry later with backoff (run_at moves forward)
MARK_RETRY = """
UPDATE jobs
SET attempts = attempts + 1,
    error = %s,
    locked_at = NULL,
    run_at = now() + make_interval(secs => %s)
WHERE id = %s
"""

# attempts exhausted: terminal failure (done_at set, error kept)
MARK_DEAD = """
UPDATE jobs
SET attempts = attempts + 1, error = %s, locked_at = NULL, done_at = now()
WHERE id = %s
"""

ENQUEUE = """
INSERT INTO jobs (kind, payload, run_at, dedupe_key)
VALUES (%s, %s, COALESCE(%s, now()), %s)
ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
RETURNING id
"""

CLEANUP_DONE = (
    "DELETE FROM jobs WHERE done_at IS NOT NULL AND done_at < now() - make_interval(days => %s)"
)
