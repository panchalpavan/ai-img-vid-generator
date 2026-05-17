"""Pollinations.ai provider — free, anonymous image generation.

URL-based API with no auth: `GET https://image.pollinations.ai/prompt/{prompt}?model=flux`
returns image bytes directly. FLUX is the default model (state-of-the-art
open-source image gen). No account, no API key, no rate-limit cliff —
**fallback of last resort** when other providers are quota-blocked.

Caveat: depends on a single org's goodwill / infrastructure. Treat as
"works today" not "guaranteed to work tomorrow." Mirrored in parking-lot
notes in docs/SPRINTS.md.

We download the image bytes server-side (in the Celery worker) and stash
them as a base64 data URI in the generations table. Alternative: store
the Pollinations URL and let the browser fetch it. Server-side fetch is
slower upfront but means the result is persisted independent of
Pollinations staying up.
"""

import base64
import urllib.parse
import urllib.request

from app.providers.types import GenerationInput, GenerationOutput, OutputType

_BASE_URL = "https://image.pollinations.ai/prompt"
_TIMEOUT_SECONDS = 90  # Pollinations can take 20-60s for FLUX
_DEFAULT_WIDTH = 1024
_DEFAULT_HEIGHT = 1024

# Pollinations' edge layer (Cloudflare) 403s unrecognised User-Agents like
# Python's default `Python-urllib/3.x`. A real-looking UA + a Referer
# identifies us as a legit client. The `referrer` query param is
# Pollinations' own free-tier "tell us who you are" mechanism — they
# allowlist known referrers for higher rate limits.
_USER_AGENT = "img-vid-generation/0.1 (+https://img-vid-generation.local)"
_REFERRER = "img-vid-generation"


class PollinationsAdapter:
    """Adapter that calls Pollinations.ai's URL-based image API."""

    def generate(self, model_id: str, inputs: GenerationInput) -> GenerationOutput:
        if not inputs.text:
            raise ValueError("Pollinations requires a text prompt.")

        # Convention: model_id is `pollinations-<model>`, e.g. `pollinations-flux`.
        # The model name after the prefix maps directly to Pollinations'
        # ?model= query parameter.
        model_name = model_id.removeprefix("pollinations-") or "flux"

        params = urllib.parse.urlencode(
            {
                "model": model_name,
                "width": _DEFAULT_WIDTH,
                "height": _DEFAULT_HEIGHT,
                "nologo": "true",
                "referrer": _REFERRER,
            }
        )
        # Pollinations encodes the prompt as the path; spaces and special
        # characters must be percent-encoded.
        path = urllib.parse.quote(inputs.text, safe="")
        url = f"{_BASE_URL}/{path}?{params}"

        # stdlib urllib avoids adding a new runtime dep just for one HTTP
        # GET. `nosec`-style note: this URL is constructed from a trusted
        # constant + user input encoded via urllib.parse.quote.
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": _USER_AGENT,
                "Accept": "image/*",
                "Referer": "https://img-vid-generation.local/",
            },
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            mime_type = response.headers.get("Content-Type", "image/jpeg")
            data: bytes = response.read()

        if not data:
            raise RuntimeError("Pollinations returned an empty response.")

        b64 = base64.b64encode(data).decode("ascii")
        return GenerationOutput(
            output_type=OutputType.IMAGE,
            url=f"data:{mime_type};base64,{b64}",
        )
