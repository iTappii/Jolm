-- Own crowd data (Ш-47, SSOT §7.3; TECH_PLAN §2 п.5): "I am here" check-ins and crowd reports
-- ("busy / normal / empty") from people who are at the place, and the aggregate the card and
-- the planner read.
--
-- Raw reports are personal data: `user_id` is NOT NULL and ON DELETE CASCADE, so DELETE /v1/me
-- removes them. No coordinates are stored, only the distance to the place at the time of the
-- report. `place_id` has NO ON DELETE CASCADE: data/osm/merge.py `merge_place` re-points the
-- reports and drops the dropped place's profile rows (TECH_PLAN rule 8).
--
-- kind: 'checkin' ("I am here", no level; feeds the visit metric of Ш-50) | 'crowd' (level
-- 0 empty, 1 normal, 2 busy).
CREATE TABLE place_crowd_reports (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    place_id    uuid        NOT NULL REFERENCES places,
    user_id     uuid        NOT NULL REFERENCES users ON DELETE CASCADE,
    kind        text        NOT NULL CHECK (kind IN ('checkin', 'crowd')),
    level       smallint    CHECK (level BETWEEN 0 AND 2),
    distance_m  integer     NOT NULL CHECK (distance_m >= 0),
    created_at  timestamptz NOT NULL DEFAULT now(),
    CHECK ((kind = 'crowd') = (level IS NOT NULL))
);
CREATE INDEX place_crowd_reports_place ON place_crowd_reports (place_id, created_at DESC);
CREATE INDEX place_crowd_reports_user ON place_crowd_reports (user_id, place_id, kind, created_at DESC);

-- Aggregate by local (Asia/Almaty) weekday (0 = Monday) and hour, rebuilt by the `crowd.aggregate`
-- job. level 0..1 is the decayed average of the reports; `samples` is the number of reports in
-- the cell. Derived data, no personal content.
CREATE TABLE place_crowd_profile (
    place_id   uuid             NOT NULL REFERENCES places,
    weekday    smallint         NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    hour       smallint         NOT NULL CHECK (hour BETWEEN 0 AND 23),
    level      double precision NOT NULL CHECK (level BETWEEN 0 AND 1),
    samples    integer          NOT NULL CHECK (samples > 0),
    updated_at timestamptz      NOT NULL DEFAULT now(),
    PRIMARY KEY (place_id, weekday, hour)
);
