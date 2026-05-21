"""Data shapes for the AI provider abstraction (ADR-0005).

`ModelConfig` is the contract the frontend sees via GET /models. It's
designed so the form-rendering logic in `apps/web` can be entirely
config-driven: read `input_types`, render those inputs. Read `output_type`,
render that kind of result. No special-casing per provider.

Vocabulary:
- "Provider" = the company/service (Google AI Studio, Vertex AI, Sjinn).
- "Model" = a specific generation system (gemini-2.0-flash, sora-2, veo-3).
- "ModelConfig" = our metadata about a model.
- "ProviderAdapter" = code that knows how to call one provider's API.

One adapter can serve multiple models (e.g., a single GoogleAIStudioAdapter
handles both gemini-2.0-flash and gemini-1.5-pro).
"""

from enum import StrEnum

from pydantic import BaseModel


class ProviderName(StrEnum):
    """The AI services we can route to."""

    GOOGLE_AI_STUDIO = "google-ai-studio"
    VERTEX_AI = "vertex-ai"
    SJINN = "sjinn"
    POLLINATIONS = "pollinations"
    CLOUDFLARE_WORKERS_AI = "cloudflare-workers-ai"
    SEEGEN = "seegen"


class InputType(StrEnum):
    """Kinds of input a model can accept.

    Drives the dynamic form on the frontend: each entry in
    ModelConfig.input_types becomes a form field.
    """

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class OutputType(StrEnum):
    """Kind of output a model produces."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"


class ModelConfig(BaseModel):
    """Frontend-visible metadata about one model.

    Returned as a list from GET /models. The frontend uses this to:
      - populate the model dropdown (display_name)
      - render the right form fields (input_types)
      - display the cost (cost_in_credits)
      - decide whether to poll for an async result (is_async)
    """

    id: str
    provider: ProviderName
    display_name: str
    input_types: list[InputType]
    output_type: OutputType
    cost_in_credits: int
    is_async: bool
    # Soft-disable switch: registered models with enabled=False stay in the
    # registry (code intact) but are hidden from GET /models and rejected by
    # POST /generations. Use for quota-blocked or experimental models we don't
    # want to delete.
    enabled: bool = True


class GenerationInput(BaseModel):
    """User-supplied inputs for a generation request.

    Fields are all optional — which apply depends on the selected model's
    input_types. Validation that the right fields are present happens in
    the /generations endpoint.
    """

    text: str | None = None
    image_urls: list[str] = []  # populated in Sprint 4 (Reference Library)


class GenerationOutput(BaseModel):
    """Result of a synchronous generation call.

    Sprint 3 will add an async variant (`JobHandle`) for providers like
    Sjinn that return a task ID instead of a finished result.
    """

    output_type: OutputType
    text: str | None = None  # set when output_type == TEXT
    url: str | None = None   # set when output_type == IMAGE | VIDEO (R2 URL)
