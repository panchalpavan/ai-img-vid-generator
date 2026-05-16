"""Celery application instance and shared task config.

This module exposes `celery_app` for the worker process to discover. Run with:
    uv run celery -A app.tasks worker --loglevel=info
Or from repo root:
    npm run dev:worker

Tasks live in submodules under app/tasks/ and are imported here so they
register themselves on the Celery app. For now there is only a tiny `ping`
task used to smoke-test the worker; real tasks (generation, etc.) come in
Sprint 3.
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "img-vid-gen",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
)

# Reasonable production-ish defaults.
celery_app.conf.update(
    # JSON-only payloads — never use pickle (CVE-risk if broker is compromised).
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Always store + reason about times in UTC.
    timezone="UTC",
    enable_utc=True,
    # Namespace our queue so it never collides with another project's worker
    # pointed at the same Redis (paranoid, but free).
    task_default_queue="img-vid-gen",
    # When a worker picks up a task, mark it as STARTED in the result backend.
    # Lets us tell "queued" from "running" in the UI later.
    task_track_started=True,
)


@celery_app.task(name="app.tasks.ping")
def ping() -> str:
    """Trivial smoke-test task: returns 'pong'.

    Useful as a "is the worker alive and consuming jobs?" probe.
    """
    return "pong"
