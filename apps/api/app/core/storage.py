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


def head_object(key: str) -> dict[str, Any] | None:
    """Return metadata for `key` if it exists in R2, else None.

    Used by the /references/complete endpoint to verify a presigned upload
    landed before we record the row. We catch botocore's 404 specifically
    (any other error indicates a real problem and should bubble up).
    """
    from botocore.exceptions import ClientError

    _access, _secret, _endpoint, bucket, _public = _require_settings()
    try:
        # ContentLength comes back as int, LastModified as datetime, etc.
        # The full HeadObjectOutput shape lives in boto3's docs; we only
        # care about a few fields downstream.
        return _client().head_object(Bucket=bucket, Key=key)  # type: ignore[no-any-return]
    except ClientError as exc:
        # boto3 reports object-not-found as either "404" (HTTP) or "NoSuchKey"
        # (S3 error code) depending on the bucket policy and operation.
        code = exc.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def generate_presigned_upload_url(
    key: str,
    content_type: str,
    content_length: int,
    expires_in_seconds: int = 300,
) -> str:
    """Build a short-lived signed PUT URL the browser can upload to directly.

    The signature **binds the upload to the exact key, content type, and
    length** — the browser MUST send those same values or R2 rejects with
    SignatureDoesNotMatch. This is by design: a leaked signed URL can't be
    repurposed to upload a different file under a different name.

    `expires_in_seconds` defaults to 5 minutes — long enough for a user to
    pick a file and the upload to finish, short enough that a leaked URL
    can't be used by a third party hours later.

    Returns the signed URL pointing at R2's S3 endpoint (NOT the r2.dev
    public URL — that one is for reads). The browser sends the file body
    as a PUT request to this URL.
    """
    _access, _secret, _endpoint, bucket, _public = _require_settings()
    # `presigned_url` for `put_object` signs every parameter we include in
    # the Params dict. Anything the client wants to vary at upload time
    # would have to be unsigned (out of scope for our needs).
    url: str = _client().generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
            "ContentLength": content_length,
        },
        ExpiresIn=expires_in_seconds,
    )
    return url


def public_url_for(key: str) -> str:
    """Compose the public r2.dev URL for a given object key.

    Mirrors what `upload_bytes` returns. Used by the references flow so the
    backend can hand the frontend a stable read URL alongside the signed
    PUT URL, without doing an upload itself.
    """
    _access, _secret, _endpoint, _bucket, public_url = _require_settings()
    return f"{public_url.rstrip('/')}/{key}"


def configure_cors(allowed_origins: list[str]) -> None:
    """Set the bucket's CORS policy.

    Required so the browser can PUT directly to R2's S3 endpoint from a
    different origin (e.g. http://localhost:3000). Without this rule, the
    browser's preflight OPTIONS request fails and the upload never starts.

    Idempotent — calling this with the same input is a no-op from the
    bucket's perspective. We expose it as a setup helper rather than
    running on every app start to avoid churn.

    The rule allows PUT and GET, with the headers a browser typically sends
    for a multipart-style direct upload (Content-Type, Content-Length, and
    any custom headers we add later). `ExposeHeaders` lets the client read
    ETag back, which is useful for client-side dedup or integrity checks.
    """
    _access, _secret, _endpoint, bucket, _public = _require_settings()
    _client().put_bucket_cors(
        Bucket=bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": allowed_origins,
                    "AllowedMethods": ["PUT", "GET", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )
