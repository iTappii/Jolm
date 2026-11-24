-- Ш-62: legs of the live route between far stops come from the intercity service (SSOT §5.4 п. 7).
-- mode: plane | train | bus_intercity | car | tour in addition to walk | transit | car;
-- an intercity leg also keeps the price range of the chosen way (NULL when unknown).
ALTER TABLE chat_live_stops DROP CONSTRAINT chat_live_stops_leg_mode_check;
ALTER TABLE chat_live_stops ADD CONSTRAINT chat_live_stops_leg_mode_check
    CHECK (leg_mode IN ('walk', 'transit', 'car', 'plane', 'train', 'bus_intercity', 'tour'));
ALTER TABLE chat_live_stops
    ADD COLUMN leg_intercity boolean NOT NULL DEFAULT false,
    ADD COLUMN leg_price_kzt_min integer CHECK (leg_price_kzt_min >= 0),
    ADD COLUMN leg_price_kzt_max integer CHECK (leg_price_kzt_max >= 0);
