"""Provider adapter contracts + the model registry.

Two structural Protocols here, one per execution model:

  - `SyncProviderAdapter` — for providers whose generations complete in a
    single round trip (Pollinations: ~3-5s, Gemini text: ~1-2s). Adapter
    exposes `generate(model_id, inputs) -> GenerationOutput`.

  - `AsyncProviderAdapter` — for providers that hand back a job ID
    immediately and require polling for the result (Seegen: 15-60s,
    Sjinn (when added): minutes for video). Adapter exposes
    `submit_async(model_id, inputs) -> str` (returns the provider's job
    id) and `poll_status(model_id, job_id) -> JobStatus`.

The Celery layer dispatches based on `ModelConfig.is_async`:
  - is_async=False → SyncProviderAdapter.generate() in the worker
  - is_async=True  → AsyncProviderAdapter.submit_async() + a separate
                     self-re-enqueueing poll task that calls
                     AsyncProviderAdapter.poll_status() periodically

Routing is config-driven, not adapter-driven — the registry stores both
the ModelConfig (which carries is_async) and the adapter instance, and
the task asks the config which path to take. An adapter that supports
both modes can implement both Protocols simultaneously; today none do.

Protocols are structural (`runtime_checkable`) so the dispatch layer can
do an `isinstance(adapter, AsyncProviderAdapter)` sanity check at routing
time and surface a clear error if a model is misconfigured (e.g.
`is_async=True` but the adapter only implements `generate`).
"""

from typing import Protocol, runtime_checkable

from app.providers.types import (
    GenerationInput,
    GenerationOutput,
    JobStatus,
    ModelConfig,
)


@runtime_checkable
class SyncProviderAdapter(Protocol):
    """Structural contract for atomic, single-round-trip providers."""

    def generate(self, model_id: str, inputs: GenerationInput) -> GenerationOutput:
        """Run a generation and return the finished result.

        Raises on provider error — the Celery task converts to a FAILED
        row with refund.
        """
        ...


@runtime_checkable
class AsyncProviderAdapter(Protocol):
    """Structural contract for job-based providers (submit then poll).

    Adapter does NOT block during the wait — `submit_async` returns
    immediately with a provider-specific job id, and the Celery layer
    drives polling via a separately-enqueued task. This keeps a single
    Celery worker from being tied up for 15-60s (or longer for video)
    per generation.
    """

    def submit_async(self, model_id: str, inputs: GenerationInput) -> str:
        """Submit the job and return the provider's job id immediately.

        Raises on submission error (auth, validation, quota). The Celery
        task converts to a FAILED row + refund, same as a sync provider
        failure.
        """
        ...

    def poll_status(self, model_id: str, job_id: str) -> JobStatus:
        """Check the job's current state without blocking.

        Returns a `JobStatus`:
          - state=PROCESSING → keep polling (caller re-enqueues)
          - state=DONE       → `output` is set; persist as usual
          - state=FAILED     → `error` is set; refund + mark FAILED

        Raises on transient query errors so the caller can decide whether
        to retry the poll (vs surfacing as a generation failure).
        """
        ...


# Union of "any adapter we know how to dispatch to." Used by the registry
# so the type system doesn't need to know which mode a given adapter
# implements — the routing layer (Celery task) inspects ModelConfig.is_async
# and calls into the appropriate Protocol.
ProviderAdapter = SyncProviderAdapter | AsyncProviderAdapter


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
