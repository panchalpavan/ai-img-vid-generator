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

from pydantic import BaseModel, ConfigDict


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
    """Result of a generation — what the provider produced.

    Returned by both synchronous adapters (`SyncProviderAdapter.generate`)
    and async adapters when polling reports the job is done
    (`JobStatus.output`).
    """

    output_type: OutputType
    text: str | None = None  # set when output_type == TEXT
    url: str | None = None   # set when output_type == IMAGE | VIDEO (R2 URL)


class JobState(StrEnum):
    """Lifecycle of an async provider job, mirrored on the row but kept as
    a separate type from GenerationStatus so the provider-status and our
    DB row-status don't accidentally drift.

    These are what a *provider* can tell us about a job. Our Generation row
    has its own status (which also includes 'pending' = row created but
    task not yet picked up — a concept the provider doesn't know about).
    """

    PROCESSING = "processing"  # submitted, still running upstream
    DONE = "done"              # output is ready
    FAILED = "failed"          # upstream reported failure


class JobStatus(BaseModel):
    """One snapshot of an async job's state, as the adapter sees it.

    `output` is populated when `state == DONE`. `error` is populated when
    `state == FAILED`. Both are None during processing.

    The Celery poll task re-enqueues itself until `state` is terminal,
    then routes to the same persistence path used by sync generations.
    """

    # Pydantic v2 is happy with strict literal defaults; this config just
    # silences "json_schema_extra" warnings for the StrEnum field.
    model_config = ConfigDict(use_enum_values=True)

    state: JobState
    output: GenerationOutput | None = None
    error: str | None = None
