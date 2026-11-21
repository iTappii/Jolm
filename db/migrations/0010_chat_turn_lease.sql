-- Chat turn lease (Ш-31 fixes). One model turn per chat at a time: a turn takes the lease with
-- UPDATE ... WHERE turn_lease_until IS NULL OR turn_lease_until < now() and clears it when the
-- turn is saved. The lease expires on its own, so a crashed process or a response that never
-- started streaming cannot block a chat for good. Works across several API processes.
ALTER TABLE chats ADD COLUMN turn_lease_until timestamptz;
