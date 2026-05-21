"""Cloudflare R2 object storage client (Sprint 4A).

R2 is **S3-compatible**, so we use boto3 — same SDK we'd use against AWS S3,
just pointed at R2's regional endpoint. The only quirks are:

  - **Endpoint URL is account-specific** (https://<ACCOUNT_ID>.r2.cloudflarestorage.com).
  - **Region must be "auto"** — R2 picks the location automatically; specifying
    a real AWS region confuses boto3.
  - **Signature v4 only.** boto3's default works.
  - **Public reads happen via a separate r2.dev subdomain**, not the API
    endpoint. We construct `https://pub-<hash>.r2.dev/<key>` URLs ourselves.

This module exposes one function — `upload_bytes()` — and one client factory.
The client is built lazily (first use) so that the app can boot when R2 isn't
configured (e.g. for backend work that doesn't touch storage); the failure
surface is moved to upload-time instead.

Why no IAM-style permissions in code: R2 API tokens are bucket-scoped at
creation time (we picked Object Read & Write + this bucket only). The token
*is* the permission boundary; we don't need to scope further at runtime.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.core.config import settings

# boto3 has no usable type stubs (the optional mypy_boto3_s3 package is a
# heavy install for marginal benefit). We treat the client as Any and rely
# on the narrow surface we actually use (put_object, delete_object).
S3Client = Any


class StorageNotConfiguredError(RuntimeError):
    """Raised when storage is used before R2 env vars are set."""


def _require_settings() -> tuple[str, str, str, str, str]:
    """Pull the five R2 env vars or raise a friendly error.

    Returns them as a tuple to keep the call sites narrow (tuple unpacking
    instead of attribute access keeps the rest of the module simple).
    """
    missing = [
        name
        for name, value in {
            "R2_ACCESS_KEY_ID": settings.r2_access_key_id,
            "R2_SECRET_ACCESS_KEY": settings.r2_secret_access_key,
            "R2_ENDPOINT": settings.r2_endpoint,
            "R2_BUCKET": settings.r2_bucket,
            "R2_PUBLIC_URL": settings.r2_public_url,
        }.items()
        if not value
    ]
    if missing:
        raise StorageNotConfiguredError(
            f"R2 storage is not configured. Missing env vars: {', '.join(missing)}. "
            "Set them in apps/api/.env and restart the app."
        )
    # Cast away Optional — we just verified all five are truthy. Asserts
    # narrow the types for mypy; at runtime they're no-ops because the loop
    # above already guarantees truthiness.
    assert settings.r2_access_key_id
    assert settings.r2_secret_access_key
    assert settings.r2_endpoint
    assert settings.r2_bucket
    assert settings.r2_public_url
    return (
        settings.r2_access_key_id,
        settings.r2_secret_access_key,
        settings.r2_endpoint,
        settings.r2_bucket,
        settings.r2_public_url,
    )


@lru_cache(maxsize=1)
def _client() -> S3Client:
    """Build the boto3 S3 client pointed at R2.

    Cached because boto3 clients are expensive to construct (TLS, signer
    setup, endpoint discovery) and are thread-safe to reuse across requests.
    """
    access_key, secret_key, endpoint, _bucket, _public = _require_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        # R2 requires SigV4 + "auto" region. Specifying any real AWS region
        # (e.g. "us-east-1") will fail signature validation against R2.
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_bytes(key: str, data: bytes, content_type: str) -> str:
    """Upload raw bytes to R2 under `key`. Returns the public URL.

    `key` is the object key (path within the bucket, no leading slash).
    Callers compose keys with a scheme like `generations/<id>.png` or
    `references/<user_id>/<id>.jpg` so the namespace stays organised.

    Returns the public r2.dev URL — what the browser uses to render the
    object via `<img src="...">`. We don't return the API endpoint URL
    because that one requires signed requests to read.
    """
    _access, _secret, _endpoint, bucket, public_url = _require_settings()
    _client().put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
        # Cache aggressively — generated images are content-addressed by id,
        # so they're effectively immutable. 1 year matches AWS guidance.
        CacheControl="public, max-age=31536000, immutable",
    )
    return f"{public_url.rstrip('/')}/{key}"


def delete_object(key: str) -> None:
    """Delete `key` from R2. No-op if it doesn't exist.

    Used by Sprint 4A.3 when the user removes an uploaded reference, and
    later if we add cleanup for failed generations.
    """
    _access, _secret, _endpoint, bucket, _public = _require_settings()
    _client().delete_object(Bucket=bucket, Key=key)
