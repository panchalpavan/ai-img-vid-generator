"""Cloudflare Workers AI — synchronous image generation on CF's edge.

Cloudflare exposes a hosted-inference API at:

  POST https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}

Bearer-authenticated with a Workers-AI-scoped token. **Same Cloudflare
account that owns the R2 bucket**, but a separate API token — R2 tokens
are bucket-scoped and don't carry inference permissions.

Why register this provider:
  - Real reliable free tier (~25-100 images/day at 10k neurons), not
    "works today because the maintainer is generous" like Pollinations.
  - FLUX-1-schnell quality is on par with FLUX-1-pro at much lower latency
    (~3-5s, designed for low step counts).
  - Slots into the existing cascade between Seegen ($) and Pollinations
    (free-but-flaky).

This adapter is **synchronous** — single round-trip, returns a base64 PNG
in the JSON body. FLUX-schnell is fast enough (~3-5s) that the worker
slot held for the duration is acceptable. If we ever switch to a slower
model that needs polling, we'd implement AsyncProviderAdapter instead;
the registry config drives that choice.

Response shape (FLUX-1-schnell):
  {
    "result": {"image": "<base64-PNG>"},
    "success": true,
    "errors": [],
    "messages": []
  }
"""

import base64
import binascii
import json
import urllib.error
import urllib.request
from typing import Any

from app.providers.types import GenerationInput, GenerationOutput, OutputType

_BASE_URL = "https://api.cloudflare.com/client/v4/accounts"
_HTTP_TIMEOUT_SECONDS = 60  # FLUX-schnell is fast (~3-5s); ceiling for safety


class CloudflareWorkersAIAdapter:
    """Adapter for Cloudflare Workers AI's hosted inference API."""

    def __init__(self, account_id: str | None, api_token: str | None) -> None:
        # Stored lazily so the app can boot with these unset — the model
        # registration in app/providers/__init__.py skips registering this
        # adapter when either is missing.
        self._account_id = account_id
        self._api_token = api_token

    def generate(self, model_id: str, inputs: GenerationInput) -> GenerationOutput:
        if not self._account_id or not self._api_token:
            raise RuntimeError(
                "Cloudflare Workers AI is not configured. "
                "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_WORKERS_AI_TOKEN."
            )
        if not inputs.text:
            raise ValueError("Cloudflare Workers AI requires a text prompt.")

        # Convention: model_id is `cloudflare-<short-name>` mapping to the
        # CF model slug. Example: `cloudflare-flux-schnell` →
        # `@cf/black-forest-labs/flux-1-schnell`. Kept as an explicit map
        # rather than string-mangling so adding new models is a single
        # dict entry and the slug-shape is documented in one place.
        cf_model = _resolve_cf_model(model_id)

        body: dict[str, Any] = {"prompt": inputs.text}
        # FLUX-schnell is optimised for 4 steps; default config gets you
        # ~3-second generations. Other models may want different defaults.
        if cf_model.endswith("flux-1-schnell"):
            body["steps"] = 4

        url = f"{_BASE_URL}/{self._account_id}/ai/run/{cf_model}"
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as resp:  # noqa: S310
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            # CF's error body is informative (auth, quota, invalid model).
            # Surface it; the frontend's parseError() maps common codes to
            # friendlier copy.
            body_str = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Cloudflare Workers AI HTTP {exc.code}: {body_str[:500]}"
            ) from exc

        return _parse_image_response(raw, cf_model)


_MODEL_ID_TO_CF_SLUG = {
    "cloudflare-flux-schnell": "@cf/black-forest-labs/flux-1-schnell",
    # Add more as we register them. Keeping this as an explicit map
    # protects us against typos in model_id from leaking upstream.
}


def _resolve_cf_model(model_id: str) -> str:
    """Translate our internal model_id to Cloudflare's `@cf/...` slug."""
    cf_model = _MODEL_ID_TO_CF_SLUG.get(model_id)
    if cf_model is None:
        raise RuntimeError(
            f"No Cloudflare Workers AI mapping for model_id {model_id!r}. "
            f"Known: {sorted(_MODEL_ID_TO_CF_SLUG)}"
        )
    return cf_model


def _parse_image_response(raw: bytes, cf_model: str) -> GenerationOutput:
    """Pull the base64 PNG out of CF's JSON response.

    FLUX-schnell returns:
      {"result": {"image": "<base64>"}, "success": true, "errors": [...]}

    We convert that to a `data:image/png;base64,...` URI — the same shape
    Pollinations produces — so the downstream R2-upload step in
    `app/tasks/generation.py:_persist_image_to_r2` handles it identically.
    """
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Cloudflare Workers AI returned non-JSON (model {cf_model!r}): {raw[:200]!r}"
        ) from exc

    if not isinstance(parsed, dict) or not parsed.get("success"):
        errors = parsed.get("errors") if isinstance(parsed, dict) else None
        raise RuntimeError(
            f"Cloudflare Workers AI reported failure (model {cf_model!r}): {errors!r}"
        )

    result = parsed.get("result")
    if not isinstance(result, dict):
        raise RuntimeError(
            f"Cloudflare Workers AI returned no result object (model {cf_model!r})"
        )

    image_b64 = result.get("image")
    if not isinstance(image_b64, str) or not image_b64:
        raise RuntimeError(
            f"Cloudflare Workers AI returned no image (model {cf_model!r})"
        )

    # Decode once to validate base64 AND sniff the actual image format —
    # Cloudflare's docs say "PNG" but FLUX-1-schnell actually returns JPEG
    # in practice (magic bytes \xff\xd8\xff). Mislabeling the MIME would
    # confuse downstream R2 storage + browsers; sniff the format and
    # build the data URI honestly.
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError(
            f"Cloudflare Workers AI image was not valid base64: {exc}"
        ) from exc

    mime = _sniff_image_mime(image_bytes)
    return GenerationOutput(
        output_type=OutputType.IMAGE,
        url=f"data:{mime};base64,{image_b64}",
    )


# Magic-byte → MIME map for the formats we expect from image-gen providers.
# Order matters for substring overlap (WebP is RIFF-then-WEBP); we use
# startswith for everything and check WebP separately because its magic
# bytes have a 4-byte file-size in between.
def _sniff_image_mime(data: bytes) -> str:
    """Return the MIME type matching `data`'s magic bytes; default to PNG.

    Defaulting to PNG (vs application/octet-stream) keeps a misidentified
    image still browser-renderable in the worst case — browsers are
    forgiving with image MIME types, and PNG is the most universally
    supported.
    """
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"
