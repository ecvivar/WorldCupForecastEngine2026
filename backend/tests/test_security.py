from jose import jwt

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)

settings = get_settings()


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "supersecret123"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False


class TestJWT:
    def test_create_access_token(self):
        token = create_access_token({"sub": "user123"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user123"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "user123"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"

    def test_decode_token(self):
        token = create_access_token({"sub": "user456", "role": "admin"})
        payload = decode_token(token)
        assert payload["sub"] == "user456"
        assert payload["role"] == "admin"

    def test_decode_invalid_token(self):
        from fastapi import HTTPException
        try:
            decode_token("invalid.token.here")
            assert False, "Should have raised"
        except HTTPException:
            pass
