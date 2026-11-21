-- Memory notes (Ш-41; SSOT §8): a short LLM-written summary of what a signed-in person said and
-- liked in a chat, fed back to the model as DATA in later chats. Guests have none.
--
-- Personal data: rows hang off users with ON DELETE CASCADE (DELETE /v1/me removes them).
-- No place ids on purpose: the note is plain text, so data/osm/merge.py has nothing to re-point
-- (TECH_PLAN rule 8 does not apply). One note per chat (updated in place when the chat is
-- summarised again); the code keeps only the newest few notes per user.
-- `chat_id` / `trip_id` are informational and outlive the chat / trip (ON DELETE SET NULL).
CREATE TABLE user_memory_notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users ON DELETE CASCADE,
    chat_id uuid REFERENCES chats ON DELETE SET NULL,
    trip_id uuid REFERENCES trips ON DELETE SET NULL,
    note text NOT NULL CHECK (char_length(note) BETWEEN 1 AND 1000),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX user_memory_notes_chat ON user_memory_notes (chat_id) WHERE chat_id IS NOT NULL;
CREATE INDEX user_memory_notes_user ON user_memory_notes (user_id, updated_at DESC);
