from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config import settings

PASSWORD_HASH_NAME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 120_000


def base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), PASSWORD_ITERATIONS)
    return f"{PASSWORD_HASH_NAME}${PASSWORD_ITERATIONS}${salt}${base64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        name, iterations_text, salt, expected = password_hash.split("$", 3)
        if name != PASSWORD_HASH_NAME:
            return False
        iterations = int(iterations_text)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), iterations)
    return hmac.compare_digest(base64url_encode(digest), expected)


def sign_token(header: dict[str, Any], payload: dict[str, Any]) -> str:
    header_part = base64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    payload_part = base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(settings.auth_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{base64url_encode(signature)}"


def create_access_token(*, subject: str, role: str, tenant_id: str) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    token = sign_token(
        {"alg": "HS256", "typ": "JWT"},
        {
            "sub": subject,
            "role": role,
            "tenant_id": tenant_id,
            "exp": int(expires_at.timestamp()),
        },
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected_signature = hmac.new(settings.auth_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(base64url_encode(expected_signature), signature_part):
        raise ValueError("Invalid token signature")

    payload = json.loads(base64url_decode(payload_part).decode("utf-8"))
    expires_at = int(payload.get("exp", 0))
    if expires_at <= int(datetime.now(UTC).timestamp()):
        raise ValueError("Token expired")
    return payload
