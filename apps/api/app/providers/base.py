"""Abstract base classes and the model registry.

The registry is the lookup table the rest of the app uses: model_id in,
(ModelConfig, ProviderAdapter) out. Adapters are protocols (structural),
not subclasses — any class that implements the right method shape works.
"""

from typing import Protocol

from app.providers.types import GenerationInput, GenerationOutput, ModelConfig


class ProviderAdapter(Protocol):
    """Structural contract every provider implementation must satisfy.

    Sprint 2 uses only `generate` (sync). Sprint 3 will extend with
    `submit_async` + `poll_status` for providers like Sjinn that return
    a job ID instead of a finished result.
    """

    def generate(self, model_id: str, inputs: GenerationInput) -> GenerationOutput:
        """Run a generation synchronously.

        Returns the finished result. Raises on provider errors — the
        /generations endpoint translates those to HTTP 4xx/5xx.
        """
        ...


class _RegistryEntry:
    """Internal: pairs a model's metadata with the adapter that can run it."""

    __slots__ = ("config", "adapter")

    def __init__(self, config: ModelConfig, adapter: ProviderAdapter) -> None:
        self.config = config
        self.adapter = adapter


class ModelRegistry:
    """Process-wide lookup table of registered models.

    One instance lives at `app.providers.registry`. Provider modules
    register themselves at import time inside `app.providers.__init__`.
    """

    def __init__(self) -> None:
        self._entries: dict[str, _RegistryEntry] = {}

    def register(self, config: ModelConfig, adapter: ProviderAdapter) -> None:
        if config.id in self._entries:
            raise ValueError(f"Model {config.id!r} is already registered")
        self._entries[config.id] = _RegistryEntry(config, adapter)

    def get(self, model_id: str) -> tuple[ModelConfig, ProviderAdapter]:
        """Look up a model by id. Raises KeyError if unknown."""
        entry = self._entries.get(model_id)
        if entry is None:
            raise KeyError(f"Unknown model id: {model_id!r}")
        return entry.config, entry.adapter

    def all_configs(self) -> list[ModelConfig]:
        """Every registered model's metadata. Used by GET /models."""
        return [entry.config for entry in self._entries.values()]
