-- Ш-69: main places on the map (SSOT §13 "Главные места на карте"): a short curated list of sights whose
-- labels the map shows from a zoom level. A separate table, not columns on `places`: the list is tiny (tens
-- of rows), curated apart from the OSM import (which rewrites places), and its own data (source, as_of)
-- must not mix with place facts. Deleting a place removes its mark. `rank` is the importance inside a
-- region (1 = most important); `min_zoom` is the map zoom from which the label is shown.
CREATE TABLE landmarks (
    place_id uuid PRIMARY KEY REFERENCES places (id) ON DELETE CASCADE,
    rank     integer NOT NULL CHECK (rank >= 1),
    min_zoom real    NOT NULL CHECK (min_zoom BETWEEN 0 AND 22),
    icon     text    NOT NULL CHECK (icon ~ '^[a-z][a-z0-9_]*$'),  -- key of the app's line-art drawing
    source   text    NOT NULL,
    as_of    date    NOT NULL
);
