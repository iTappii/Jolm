-- Account deletion (Ш-28): hard-delete users, cascade personal data.

-- Encrypted Sign in with Apple refresh token (Fernet ciphertext); needed to revoke the grant when
-- the account is deleted (App Store requirement). NULL when Apple credentials were not configured.
ALTER TABLE auth_identities ADD COLUMN provider_refresh_token text;

-- User-authored photos survive account deletion, anonymized (author becomes NULL).
UPDATE place_photos SET author_user_id = NULL
WHERE author_user_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM users WHERE users.id = place_photos.author_user_id);
ALTER TABLE place_photos
    ADD CONSTRAINT place_photos_author_fk
    FOREIGN KEY (author_user_id) REFERENCES users (id) ON DELETE SET NULL;
