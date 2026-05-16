"""AI provider registry — single source of truth for which models exist.

Importing this module has the side effect of registering every model on
`registry`. Add a new model: instantiate its adapter, build a ModelConfig,
call `registry.register(config, adapter)`. Nothing else changes — the
frontend form, /generations endpoint, and credit logic all read from
`registry` and don't know what providers exist.
"""

from app.core.config import settings
from app.providers.base import ModelRegistry, ProviderAdapter
from app.providers.google_ai_studio import GoogleAIStudioAdapter
from app.providers.types import (
    GenerationInput,
    GenerationOutput,
    InputType,
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


# Public re-exports for routers and other consumers.
__all__ = [
    "GenerationInput",
    "GenerationOutput",
    "InputType",
    "ModelConfig",
    "OutputType",
    "ProviderAdapter",
    "ProviderName",
    "registry",
]
