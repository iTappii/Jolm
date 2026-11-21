# Leasing (review Ш-01-03-06 №2-4). A claim is its own short transaction: it stamps `locked_at`
# (clock_timestamp(): distinct per row, doubles as the owner token) and counts the attempt NOW, so
# a worker that dies mid-job still burns an attempt. A job whose lease ran out (locked_at older
# than the lease, params: lease seconds) is due again; completion statements below only act on the
# row if `locked_at` is still the claimer's token. params: lease_sec, limit.
CLAIM = """
UPDATE jobs SET locked_at = clock_timestamp(), attempts = attempts + 1
WHERE id IN (
    SELECT id FROM jobs
    WHERE run_at <= now() AND done_at IS NULL
      AND (locked_at IS NULL OR locked_at < now() - make_interval(secs => %s))
    ORDER BY run_at
    FOR UPDATE SKIP LOCKED
    LIMIT %s
)
RETURNING id, kind, payload, attempts, locked_at
"""

# A job that keeps killing its worker: lease expired and no attempts left -> terminal failure,
# payload cleared. params: lease_sec, max_attempts.
REAP_EXHAUSTED = """
UPDATE jobs
SET done_at = now(), locked_at = NULL, payload = '{}'::jsonb,
    error = 'lease expired: the worker did not finish the job'
WHERE done_at IS NULL AND locked_at < now() - make_interval(secs => %s) AND attempts >= %s
"""

# params: id, locked_at (the claimer's token). The payload may hold secrets (the encrypted Apple
# token of `apple.revoke`): it is wiped when the job ends, done or dead.
MARK_DONE = """
UPDATE jobs
SET done_at = now(), error = NULL, locked_at = NULL, payload = '{}'::jsonb
WHERE id = %s AND locked_at = %s AND done_at IS NULL
RETURNING id
"""

# retry later with backoff (run_at moves forward); the attempt was counted at claim.
# params: error, backoff seconds, id, locked_at
MARK_RETRY = """
UPDATE jobs
SET error = %s, locked_at = NULL, run_at = now() + make_interval(secs => %s)
WHERE id = %s AND locked_at = %s AND done_at IS NULL
RETURNING id
"""

# attempts exhausted: terminal failure (done_at set, error kept, payload wiped)
# params: error, id, locked_at
MARK_DEAD = """
UPDATE jobs
SET error = %s, locked_at = NULL, done_at = now(), payload = '{}'::jsonb
WHERE id = %s AND locked_at = %s AND done_at IS NULL
RETURNING id
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
