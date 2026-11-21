-- Ш-37 follow-up: which path variant (Ш-22a) of the chosen transport mode a leg uses.
-- 0 = the optimal variant (what the planner stores); the person can pick 1 or 2 per leg.
ALTER TABLE trip_legs ADD COLUMN chosen_variant integer NOT NULL DEFAULT 0 CHECK (chosen_variant >= 0);
