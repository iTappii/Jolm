-- Open-Meteo forecast cache (Ш-39, SSOT §7.1): one row per rounded point and local day.
--
-- Shared by the API and the worker and kept across restarts, so the free API quota is spent on
-- distinct places and days, not on processes. TTL (about 3 hours) is applied when reading:
-- `fetched_at` decides, old rows are overwritten by the next fetch (no cleanup job needed; a
-- row is a few KB and the key space is a handful of Almaty points x 16 days).
--
-- No personal data and no place references: the key is a coordinate rounded to 0.01 degree
-- (about 1 km) and, for mountain places, the elevation rounded to 100 m (Open-Meteo corrects
-- the temperature to the given elevation). `elevation_key` -1 = no elevation was passed.
-- `hourly` is a JSON array of 24 local hours (Asia/Almaty): {"t": temp C, "p": precipitation
-- probability 0..1, "mm": precipitation mm, "w": wind km/h, "c": WMO weather code}, null = unknown.

CREATE TABLE weather_cache (
    lat_e2 integer NOT NULL,
    lon_e2 integer NOT NULL,
    elevation_key integer NOT NULL DEFAULT -1,
    day date NOT NULL,
    hourly jsonb NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (lat_e2, lon_e2, elevation_key, day)
);
CREATE INDEX weather_cache_fetched ON weather_cache (fetched_at);
