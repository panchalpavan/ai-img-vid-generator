"""AI provider registry — single source of truth for which models exist.

Importing this module has the side effect of registering every model on
`registry`. Add a new model: instantiate its adapter, build a ModelConfig,
call `registry.register(config, adapter)`. Nothing else changes — the
frontend form, /generations endpoint, and credit logic all read from
`registry` and don't know what providers exist.
"""

from app.core.config import settings
from app.providers.base import (
    AsyncProviderAdapter,
    ModelRegistry,
    ProviderAdapter,
    SyncProviderAdapter,
)
from app.providers.cloudflare_workers_ai import CloudflareWorkersAIAdapter
from app.providers.google_ai_studio import GoogleAIStudioAdapter
from app.providers.pollinations import PollinationsAdapter
from app.providers.seegen import SeegenAdapter
from app.providers.types import (
    GenerationInput,
    GenerationOutput,
    InputType,
    JobState,
    JobStatus,
    ModelConfig,
    OutputType,
    ProviderName,
)

# Process-wide registry. Mutated below by registration calls, then read by
# /generations and /models. Module-level state is fine because models are
# defined once at boot and never change at runtime.
registry = ModelRegistry()


# ---- Google AI Studio: Gemini --------------------------------------------
_google_adapter = GoogleAIStudioAdapter(api_key=settings.google_api_key)

registry.register(
    ModelConfig(
        id="gemini-2.5-flash",
        provider=ProviderName.GOOGLE_AI_STUDIO,
        display_name="Gemini 2.5 Flash",
        input_types=[InputType.TEXT],
        output_type=OutputType.TEXT,
        cost_in_credits=1,
        is_async=False,
    ),
    _google_adapter,
)

registry.register(
    ModelConfig(
        id="gemini-2.5-flash-image",
        provider=ProviderName.GOOGLE_AI_STUDIO,
        display_name="Gemini 2.5 Flash Image (Nano Banana)",
        input_types=[InputType.TEXT],
        output_type=OutputType.IMAGE,
        # Higher cost than text — generating an image uses more compute.
        # Round number for now; we can revisit when Stripe-priced credits
        # exist (Sprint 5).
        cost_in_credits=2,
        is_async=False,
        # Disabled: user's AI Studio free tier has `limit: 0` for this model.
        # Flip back to True if/when quota is granted.
        enabled=False,
    ),
    _google_adapter,
)


# ---- Seegen.ai: job-based image generation, metered free tier ----------
# 200 credits at signup; 2k/medium ≈ 35 of their credits per image, so the
# free tier is ~5 test images. Adapter blocks (polls internally) so the rest
# of the app treats it as synchronous.
_seegen_adapter = SeegenAdapter(api_key=settings.seegen_api_key)

registry.register(
    ModelConfig(
        id="seegen-gpt-image-2",
        provider=ProviderName.SEEGEN,
        display_name="Seegen GPT-Image-2 (1k, medium)",
        input_types=[InputType.TEXT],
        output_type=OutputType.IMAGE,
        cost_in_credits=2,
        # Sprint 6.3 — Seegen's adapter now implements AsyncProviderAdapter
        # (submit_async + poll_status). Celery dispatches to the async
        # path: submit, return immediately, poll task re-enqueues itself
        # until terminal. Worker slots stop blocking on long generations.
        is_async=True,
    ),
    _seegen_adapter,
)


# ---- Cloudflare Workers AI: free reliable image generation -------------
# Registers only when BOTH env vars are set. Skipping the registration
# (vs registering with disabled=True) keeps the model out of /models
# entirely when CF isn't configured — no misleading "unavailable" entry.
if settings.cloudflare_account_id and settings.cloudflare_workers_ai_token:
    _cf_workers_ai_adapter = CloudflareWorkersAIAdapter(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_workers_ai_token,
    )
    registry.register(
        ModelConfig(
            id="cloudflare-flux-schnell",
            provider=ProviderName.CLOUDFLARE_WORKERS_AI,
            display_name="Cloudflare FLUX-1 Schnell (free)",
            input_types=[InputType.TEXT],
            output_type=OutputType.IMAGE,
            cost_in_credits=2,
            is_async=False,
        ),
        _cf_workers_ai_adapter,
    )


# ---- Pollinations.ai: free FLUX-backed image generation, no auth -------
# Last-resort fallback when other providers are quota-blocked. See
# parking-lot notes in docs/SPRINTS.md for the cascade strategy.
_pollinations_adapter = PollinationsAdapter()

registry.register(
    ModelConfig(
        id="pollinations-flux",
        provider=ProviderName.POLLINATIONS,
        display_name="Pollinations FLUX (free, no auth)",
        input_types=[InputType.TEXT],
        output_type=OutputType.IMAGE,
        cost_in_credits=2,
        is_async=False,
    ),
    _pollinations_adapter,
)


# Public re-exports for routers and other consumers.
__all__ = [
    "AsyncProviderAdapter",
    "GenerationInput",
    "GenerationOutput",
    "InputType",
    "JobState",
    "JobStatus",
    "ModelConfig",
    "OutputType",
    "ProviderAdapter",
    "ProviderName",
    "SyncProviderAdapter",
    "registry",
]
