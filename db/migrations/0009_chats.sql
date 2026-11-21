-- Registered-user chat and trip brief (Ш-31). Guest chats are never stored (SSOT §3.1).
-- Everything here is personal data: all rows hang off users with ON DELETE CASCADE, so deleting
-- the account (Ш-28) removes chats, messages, briefs and graph nodes.
-- No place_id columns on purpose: places mentioned in a chat are not stored (they are looked up
-- live); TECH_PLAN rule 8 (merge_place) therefore does not apply. The planner (Ш-33+) will add
-- its own tables with place references.

CREATE TABLE chats (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    title text,
    locale text NOT NULL DEFAULT 'en' CHECK (locale IN ('ru','en')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chats_user_updated ON chats (user_id, updated_at DESC, id);

CREATE TABLE chat_messages (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,  -- also the order inside a chat
    chat_id uuid NOT NULL REFERENCES chats ON DELETE CASCADE,
    role text NOT NULL CHECK (role IN ('user','assistant')),
    content text NOT NULL DEFAULT '',
    -- assistant only: audit of tools the model called, [{name, arguments, ok, error?}]
    tool_calls jsonb,
    -- assistant only
    prompt_id text,  -- e.g. trip_brief.ru.v1
    finish text CHECK (finish IN ('stop','interrupted','error')),
    input_tokens integer,
    output_tokens integer,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX chat_messages_chat ON chat_messages (chat_id, id);

-- One brief per chat, created together with the chat. Money in integer tenge for the WHOLE trip;
-- dates are calendar dates in Asia/Almaty. NULL = not known yet.
CREATE TABLE trip_briefs (
    chat_id uuid PRIMARY KEY REFERENCES chats ON DELETE CASCADE,
    start_date date,
    end_date date,
    budget_kzt bigint CHECK (budget_kzt > 0),
    has_accommodation boolean,
    must_haves jsonb NOT NULL DEFAULT '[]',
    interests jsonb NOT NULL DEFAULT '[]',
    pace text CHECK (pace IN ('calm','normal','dense')),
    crowd_tolerance smallint CHECK (crowd_tolerance BETWEEN 0 AND 4),  -- 0 quiet only .. 4 any
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (start_date IS NULL OR end_date IS NULL OR end_date >= start_date)
);

-- Single-branch graph of short theses (SSOT §11.2); `ord` grows by one per node.
-- The text is stored in the chat's language (the model writes it; no translation is stored).
CREATE TABLE chat_graph_nodes (
    chat_id uuid NOT NULL REFERENCES chats ON DELETE CASCADE,
    ord integer NOT NULL,
    kind text NOT NULL DEFAULT 'fact',
    text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (chat_id, ord)
);
