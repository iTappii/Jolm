"""Memory and personalization (Ш-41, SSOT §8). Registered users only; a guest has no memory.

- `affinity`: what the person turned down (signals of trip edits, Ш-38) and what they saved
  (favourites, Ш-23b) -> scoring inputs for the planner (Ш-33).
- `notes`: short LLM summaries of past chats (`user_memory_notes`) and the data block that
  carries them, with the affinities, into the chat.
- `jobs`: the worker handlers that write the notes.
"""
