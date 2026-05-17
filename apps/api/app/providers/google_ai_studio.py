"""Gemini provider — Google AI Studio (free tier, no GCP billing required).

Handles both text-output models (e.g., `gemini-2.5-flash`) and image-output
models (e.g., `gemini-2.5-flash-image` — "Nano Banana").

In Sprint 7 we migrate to Vertex AI for production (same models, GCP-native
auth + billing). Because both providers go through the registry, that swap
is a new adapter file + one registry entry, not a UI/pipeline rewrite.

Auth: API key from https://aistudio.google.com/apikey, stored in env as
GOOGLE_API_KEY (read by app.core.config.settings).
"""

import base64

from app.providers.types import GenerationInput, GenerationOutput, OutputType


class GoogleAIStudioAdapter:
    """Adapter for Gemini text + image models via google-generativeai SDK."""

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key
        self._configured = False

    def _ensure_configured(self) -> None:
        """Lazy one-time SDK configuration."""
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
        """Run a synchronous generation against the named Gemini model.

        Routes by model_id: anything with "image" in the name asks Gemini to
        return the IMAGE modality and we parse `inline_data` from the
        response into a base64 data URI. Other models return text.

        The data-URI approach is a Sprint 3.5 stopgap — when R2 storage
        lands, we'll upload the bytes and return an https URL. Everything
        else (registry, response shape, frontend) stays the same.
        """
        self._ensure_configured()

        if not inputs.text:
            raise ValueError("Gemini text input is required.")

        import google.generativeai as genai

        model = genai.GenerativeModel(model_id)
        is_image_model = "image" in model_id

        if is_image_model:
            # response_modalities tells Gemini to produce IMAGE bytes (and
            # optionally a TEXT description alongside, useful for alt text
            # in the future).
            response = model.generate_content(
                inputs.text,
                generation_config={"response_modalities": ["TEXT", "IMAGE"]},
            )
        else:
            response = model.generate_content(inputs.text)

        # Image path: scan the response parts for inline_data and return
        # the first image we find as a base64 data URI.
        if is_image_model and response.candidates:
            for part in response.candidates[0].content.parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    b64 = base64.b64encode(inline.data).decode("ascii")
                    return GenerationOutput(
                        output_type=OutputType.IMAGE,
                        url=f"data:{inline.mime_type};base64,{b64}",
                    )
            # Image model but no image part returned — likely the model
            # produced only text (e.g., a safety refusal). Surface that.
            return GenerationOutput(
                output_type=OutputType.TEXT,
                text=response.text or "(no image returned)",
            )

        # Text path: `response.text` raises if the response was blocked or
        # has no candidates. Let it propagate — /generations turns it into
        # an HTTP error.
        return GenerationOutput(output_type=OutputType.TEXT, text=response.text)
