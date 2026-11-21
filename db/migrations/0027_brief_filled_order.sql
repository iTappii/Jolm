-- Ш-32b: the order in which the tourist filled the brief fields. The chat ring (SSOT §11.2) draws one node per
-- answer in this order and restores it when a chat is reopened. Entries: a brief field name ("budget_kzt", …) or
-- "must_haves:<item>" for one must-have; never repeated.
ALTER TABLE trip_briefs ADD COLUMN filled_order jsonb NOT NULL DEFAULT '[]';
