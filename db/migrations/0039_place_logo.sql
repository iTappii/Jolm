-- Ш-70: a place's own logo (SSOT §6.1, §13). Only a logo uploaded by the partner or the team, with the
-- right to show it; nothing is imported from OSM or from brands. `logo_source` says who supplied it
-- ('partner' | 'team') and is required exactly when a logo is set. Both stay NULL until someone uploads.
ALTER TABLE places
    ADD COLUMN logo_key    text,
    ADD COLUMN logo_source text CHECK (logo_source IN ('partner', 'team')),
    ADD CONSTRAINT places_logo_has_source CHECK ((logo_key IS NULL) = (logo_source IS NULL));
