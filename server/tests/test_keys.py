"""Ш-51: separate secrets (JWT, OTP HMAC, Apple nonce, token encryption) and startup checks."""

import jwt
import pytest
from cryptography.fernet import Fernet, InvalidToken
from pydantic import SecretStr

from app.auth import apple_grants, keys, sessions
from app.auth.keys import SecretsError, validate
from app.config import Settings, get_settings
from app.errors import AppError

J, OT, C = "j" * 40, "o" * 40, "c" * 40


def prod(**overrides):
    values = dict(
        _env_file=None,
        app_env="prod",
        jwt_secret=J,
        otp_secret=OT,
        apple_challenge_secret=C,
        token_encryption_keys=Fernet.generate_key().decode(),
    )
    values.update(overrides)
    return Settings(**values)


def use(monkeypatch, settings):
    get_settings.cache_clear()
    monkeypatch.setattr("app.auth.keys.get_settings", lambda: settings)
    return settings


def test_prod_with_everything_set_starts():
    validate(prod())


@pytest.mark.parametrize(
    "missing", ["jwt_secret", "otp_secret", "apple_challenge_secret", "token_encryption_keys"]
)
def test_prod_refuses_a_missing_secret(missing):
    with pytest.raises(SecretsError) as err:
        validate(prod(**{missing: ""}))
    assert missing.upper() in str(err.value)


def test_prod_ignores_the_auth_secret_fallback():
    with pytest.raises(SecretsError):
        validate(prod(jwt_secret="", auth_secret="a" * 40))


def test_prod_refuses_short_shared_or_legacy_secrets():
    with pytest.raises(SecretsError, match="at least 32"):
        validate(prod(jwt_secret="short"))
    with pytest.raises(SecretsError, match="must differ"):
        validate(prod(otp_secret=J))
    with pytest.raises(SecretsError, match="AUTH_SECRET"):
        validate(prod(auth_secret=C))
    with pytest.raises(SecretsError, match="invalid Fernet"):
        validate(prod(token_encryption_keys="not-a-fernet-key"))


def test_staging_is_not_dev():
    with pytest.raises(SecretsError):
        validate(prod(app_env="staging", jwt_secret=""))


def test_dev_and_test_need_nothing():
    for env in ("dev", "test"):
        validate(Settings(_env_file=None, app_env=env))


def test_dev_falls_back_to_the_auth_secret_and_prod_does_not(monkeypatch):
    use(monkeypatch, Settings(_env_file=None, app_env="dev", auth_secret=SecretStr("a" * 40)))
    assert keys.jwt_key() == keys.otp_key() == keys.challenge_key() == b"a" * 40
    assert sessions.signing_key() == b"a" * 40
    use(monkeypatch, prod(jwt_secret="", auth_secret=SecretStr("a" * 40)))
    with pytest.raises(AppError):
        keys.jwt_key()


def test_each_purpose_has_its_own_key(monkeypatch):
    use(monkeypatch, prod())
    assert (keys.jwt_key(), keys.otp_key(), keys.challenge_key()) == (
        J.encode(),
        OT.encode(),
        C.encode(),
    )


def test_tokens_signed_with_one_purpose_key_do_not_verify_with_another(monkeypatch):
    use(monkeypatch, prod())
    forged = jwt.encode({"sub": "x"}, keys.challenge_key(), algorithm="HS256")
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(forged, keys.jwt_key(), algorithms=["HS256"])


def test_dev_encryption_is_backward_compatible_with_the_derived_key(monkeypatch):
    import base64
    import hashlib

    use(monkeypatch, Settings(_env_file=None, app_env="dev", auth_secret=SecretStr("a" * 40)))
    old = Fernet(
        base64.urlsafe_b64encode(hashlib.sha256(b"jol:apple-refresh:" + b"a" * 40).digest())
    )
    assert apple_grants.decrypt_token(old.encrypt(b"apple-token").decode()) == "apple-token"
    assert old.decrypt(apple_grants.encrypt_token("t").encode()) == b"t"


def test_key_rotation_keeps_old_ciphertexts_readable(monkeypatch):
    old_key, new_key = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    use(monkeypatch, prod(token_encryption_keys=old_key))
    stored = apple_grants.encrypt_token("refresh-1")
    use(monkeypatch, prod(token_encryption_keys="%s, %s" % (new_key, old_key)))
    assert apple_grants.decrypt_token(stored) == "refresh-1"  # old key still decrypts
    fresh = keys.rotate_ciphertext(stored)
    use(monkeypatch, prod(token_encryption_keys=new_key))  # the old key is dropped
    assert apple_grants.decrypt_token(fresh) == "refresh-1"
    with pytest.raises(apple_grants.AppleGrantError):
        apple_grants.decrypt_token(stored)  # not rotated before the key was dropped: unreadable


def test_prod_migrates_tokens_encrypted_before_with_the_legacy_secret(monkeypatch):
    import base64
    import hashlib

    old_auth = "legacy-auth-secret-of-at-least-32-bytes"
    legacy = Fernet(
        base64.urlsafe_b64encode(hashlib.sha256(b"jol:apple-refresh:" + old_auth.encode()).digest())
    )
    stored = legacy.encrypt(b"old-apple-token").decode()
    new_key = Fernet.generate_key().decode()
    use(monkeypatch, prod(token_encryption_keys=new_key))
    with pytest.raises(apple_grants.AppleGrantError):
        apple_grants.decrypt_token(stored)
    use(monkeypatch, prod(token_encryption_keys=new_key, legacy_token_secret=old_auth))
    assert apple_grants.decrypt_token(stored) == "old-apple-token"
    migrated = keys.rotate_ciphertext(stored)
    use(monkeypatch, prod(token_encryption_keys=new_key))  # legacy secret removed afterwards
    assert apple_grants.decrypt_token(migrated) == "old-apple-token"


def test_decrypt_with_wrong_key_raises(monkeypatch):
    use(monkeypatch, prod())
    other = Fernet(Fernet.generate_key()).encrypt(b"x").decode()
    with pytest.raises(InvalidToken):
        keys.decrypt(other)


async def test_lifespan_refuses_to_start_in_prod_without_secrets(monkeypatch):
    from app.main import create_app, lifespan

    monkeypatch.setattr("app.main.get_settings", lambda: prod(jwt_secret=""))
    with pytest.raises(SecretsError):
        async with lifespan(create_app()):
            pass


def test_check_cli(monkeypatch, capsys):
    use(monkeypatch, prod())
    assert keys.main(["check"]) == 0
    use(monkeypatch, prod(otp_secret=""))
    assert keys.main(["check"]) == 1
    assert "OTP_SECRET" in capsys.readouterr().out
    assert keys.main(["generate"]) == 0
    out = capsys.readouterr().out
    assert "JWT_SECRET=" in out and "TOKEN_ENCRYPTION_KEYS=" in out
