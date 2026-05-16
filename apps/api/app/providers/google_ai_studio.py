"""Gemini provider — Google AI Studio (free tier, no GCP billing required).

In Sprint 7 we migrate to Vertex AI for production (same models, GCP-native
auth + billing). Because both providers go through the registry, that swap
is a new adapter file + one registry entry, not a UI/pipeline rewrite.

Auth: API key from https://aistudio.google.com/apikey, stored in env as
GOOGLE_API_KEY (read by app.core.config.settings).
"""

from typing import TYPE_CHECKING

from app.providers.types import GenerationInput, GenerationOutput, OutputType

if TYPE_CHECKING:
    # The Google SDK is not type-checked (no stubs), so we hide its import
    # from mypy. Runtime imports happen lazily inside `generate` to avoid
    # SDK initialization at module-import time (and to make the case where
    # GOOGLE_API_KEY is unset fail at use-time, not at import-time).
    pass


class GoogleAIStudioAdapter:
    """Adapter that calls Gemini text models via google-generativeai SDK."""

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key
        self._configured = False

    def _ensure_configured(self) -> None:
        """Lazy one-time SDK configuration.

        Doing this at first-use instead of at adapter construction means the
        app boots even when GOOGLE_API_KEY is unset — useful in CI or when
        only the non-Gemini paths are exercised.
        """
        if self._configured:
            return
        if not self._api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY is not set. Get a free key at "
                "https://aistudio.google.com/apikey and add it to apps/api/.env."
            )
        import google.generativeai as genai

        genai.configure(api_key=self._api_key)
        self._configured = True

    def generate(self, model_id: str, inputs: GenerationInput) -> GenerationOutput:
        """Run a synchronous text-to-text generation against Gemini.

        Image inputs (multimodal) land in Sprint 4 with the Reference
        Library. For now: text in, text out.
        """
        self._ensure_configured()

        if not inputs.text:
            raise ValueError("Gemini text models require a 'text' input.")

        import google.generativeai as genai

        model = genai.GenerativeModel(model_id)
        response = model.generate_content(inputs.text)
        # `response.text` raises if the response was blocked or has no
        # candidates. Let it propagate — /generations turns it into HTTP 502.
        return GenerationOutput(output_type=OutputType.TEXT, text=response.text)
