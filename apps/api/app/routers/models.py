"""GET /models — returns every registered model's metadata.

Public (no auth) so the frontend can render the model dropdown even
before the user signs in. The endpoint is cheap and the data isn't
sensitive — just our list of model IDs and their input shapes.
"""

from fastapi import APIRouter

from app.providers import ModelConfig, registry

router = APIRouter()


@router.get("/models", response_model=list[ModelConfig], tags=["models"])
def list_models() -> list[ModelConfig]:
    """Return every enabled model the frontend can offer."""
    return [config for config in registry.all_configs() if config.enabled]
