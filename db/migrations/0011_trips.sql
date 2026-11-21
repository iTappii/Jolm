-- Trips built by the planner (Ш-35, Ш-36): trips, trip_items, trip_legs, trip_lodging_options.
-- Money: integer tenge (bigint). Times: timestamptz (Asia/Almaty wall-clock is applied by the
-- application); `day` is the local calendar date.
--
-- Personal data: trips hang off users with ON DELETE CASCADE (DELETE /v1/me removes them).
-- Place references (trip_items.place_id, trip_lodging_options.place_id) deliberately have NO
-- ON DELETE CASCADE: a place must not silently vanish from someone's trip. The OSM importer
-- merges duplicate places with data/osm/merge.py `merge_place`, which re-points these rows
-- (TECH_PLAN rule 8).
--
-- One trip per chat (UNIQUE chat_id): building again after edits updates the same trip and
-- increments `version`; items, legs and lodging options are replaced.
--
-- `variant`: rows with variant = 'main' are the trip's plan. When the plan does not fit the
-- budget, the two alternatives of SSOT §5.2 are stored next to it as 'drop_places' and 'cheaper'
-- rows until the user picks one (POST /v1/trips/{id}/budget-choice): the chosen variant becomes
-- 'main', the others are deleted. Readers MUST filter `variant = 'main'`.

CREATE TABLE trips (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    -- the chat the trip was built in; a trip outlives its chat (no chat deletion exists yet)
    chat_id uuid UNIQUE REFERENCES chats ON DELETE SET NULL,
    -- the brief the plan was built from (chat brief can change later); ISO dates, no ids
    brief jsonb NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL CHECK (end_date >= start_date),
    budget_kzt bigint CHECK (budget_kzt > 0),
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    weather_checked_at timestamptz,  -- Ф11
    -- wishes the plan could not honour: [{wish?, place_name?, reason}] (SSOT §16.11)
    must_have_unmet jsonb NOT NULL DEFAULT '[]',
    -- layout and budget warnings: [{code, date?, detail?}]
    warnings jsonb NOT NULL DEFAULT '[]',
    -- budget summary of the main plan and the variants' totals; no place ids inside
    budget jsonb NOT NULL DEFAULT '{}',
    total_cost_kzt bigint NOT NULL DEFAULT 0 CHECK (total_cost_kzt >= 0),
    budget_choice text CHECK (budget_choice IN ('drop_places', 'cheaper', 'keep')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX trips_user_updated ON trips (user_id, updated_at DESC, id);

CREATE TABLE trip_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    variant text NOT NULL DEFAULT 'main' CHECK (variant IN ('main', 'drop_places', 'cheaper')),
    day date NOT NULL,
    ord integer NOT NULL,  -- order inside the day, from 1
    -- no ON DELETE CASCADE on purpose (rule 8); events are Ф16 and get their own column then
    place_id uuid NOT NULL REFERENCES places,
    kind text NOT NULL CHECK (kind IN ('activity', 'meal')),
    meal text CHECK (meal IN ('lunch', 'dinner')),
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    visit_min integer NOT NULL,
    is_must_have boolean NOT NULL DEFAULT false,
    est_cost_kzt bigint NOT NULL DEFAULT 0 CHECK (est_cost_kzt >= 0),
    -- the cost is a default (average check or entry price was not in the database)
    cost_assumed boolean NOT NULL DEFAULT false,
    hours_assumed boolean NOT NULL DEFAULT false,
    rain_exposed boolean NOT NULL DEFAULT false,
    UNIQUE (trip_id, variant, day, ord),
    CHECK (ends_at > starts_at)
);
CREATE INDEX trip_items_place ON trip_items (place_id);

-- A transition into `to_item_id`; from_item_id is NULL for the leg from the day's start point.
CREATE TABLE trip_legs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trip_id uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    variant text NOT NULL DEFAULT 'main' CHECK (variant IN ('main', 'drop_places', 'cheaper')),
    from_item_id uuid REFERENCES trip_items ON DELETE CASCADE,
    to_item_id uuid NOT NULL REFERENCES trip_items ON DELETE CASCADE,
    depart_at timestamptz NOT NULL,
    -- every transport option of the Ш-22 builder (modes, time, cost, geometry); `steps` dropped
    options jsonb NOT NULL DEFAULT '[]',
    chosen_mode text,  -- the default option; NULL when no option could be computed
    travel_s integer NOT NULL,  -- time the schedule reserves
    cost_kzt integer NOT NULL DEFAULT 0,  -- upper cost of the chosen option
    estimated boolean NOT NULL DEFAULT false  -- no router options: straight-line time estimate
);
CREATE INDEX trip_legs_trip ON trip_legs (trip_id, variant);
CREATE INDEX trip_legs_to_item ON trip_legs (to_item_id);

-- Where to stay when the tourist has no lodging (SSOT §5.2): 3-5 options with the stay cost.
-- `recommended` is the option whose cost is counted in the budget. Bookings are Ф16.
CREATE TABLE trip_lodging_options (
    trip_id uuid NOT NULL REFERENCES trips ON DELETE CASCADE,
    place_id uuid NOT NULL REFERENCES places,  -- no ON DELETE CASCADE (rule 8)
    rank integer NOT NULL,
    price_per_night_kzt bigint NOT NULL CHECK (price_per_night_kzt >= 0),
    price_assumed boolean NOT NULL DEFAULT false,  -- the place has no price: a category default
    nights integer NOT NULL CHECK (nights >= 0),
    total_kzt bigint NOT NULL CHECK (total_kzt >= 0),  -- nights * price_per_night_kzt
    recommended boolean NOT NULL DEFAULT false,
    PRIMARY KEY (trip_id, place_id)
);
CREATE INDEX trip_lodging_options_place ON trip_lodging_options (place_id);
