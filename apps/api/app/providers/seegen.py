"""Seegen.ai provider — job-based image generation.

Seegen's API is **asynchronous**: POST `/jobs/createTask` returns a `taskId`
immediately, and the caller polls `/jobs/queryTask?taskId=...` until the
job reaches `COMPLETED` or `FAILED`.

This adapter implements the `AsyncProviderAdapter` Protocol (Sprint 6.3
refactor): submission and status-checking are exposed as separate
non-blocking methods, and the Celery layer drives polling via a
self-re-enqueueing task — so a single worker isn't tied up for 15-60s
per generation.

API surface (https://seegen.ai/api-docs):
  POST /api/v1/jobs/createTask    → {"taskId": "..."}
  GET  /api/v1/jobs/queryTask?taskId=...
                                  → {"status": "PENDING|PROCESSING|COMPLETED|FAILED",
                                     "output": [{"url": "..."}], "error": ...}

Pricing is metered in Seegen's *own* credit system (not ours): 1k/medium
is 15 of their credits per image. Failed tasks refund automatically on
their side. Our `cost_in_credits` field is independent — it represents
what *we* charge our user in *our* ledger.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from app.providers.types import (
    GenerationInput,
    GenerationOutput,
    JobState,
    JobStatus,
    OutputType,
)

_BASE_URL = "https://seegen.ai/api/v1"
_CREATE_PATH = "/jobs/createTask"
_QUERY_PATH = "/jobs/queryTask"

# Network timeout for a single HTTP request. NOT the same as the overall
# job-wait budget — that's controlled by the Celery poll task (it stops
# re-enqueueing after a configured elapsed time).
_HTTP_TIMEOUT_SECONDS = 30

# Seegen accepts these as inputs; we'll expose them as user-facing options in
# a later sprint once the dynamic form supports per-model parameters. For now,
# default to the cheapest tier — quality doesn't matter during development
# (15 of *their* credits per image at 1k/medium — 200 credits ≈ 13 test images).
_DEFAULT_QUALITY = "medium"
_DEFAULT_RESOLUTION = "1k"
_DEFAULT_ASPECT_RATIO = "1:1"
_DEFAULT_OUTPUT_FORMAT = "png"

# Map Seegen's lifecycle strings to our JobState enum. PENDING (queued
# but not yet started) and PROCESSING (running) both surface to us as
# "still going" — we don't need that finer-grained distinction.
_SEEGEN_TO_JOB_STATE: dict[str, JobState] = {
    "PENDING": JobState.PROCESSING,
    "PROCESSING": JobState.PROCESSING,
    "COMPLETED": JobState.DONE,
    "FAILED": JobState.FAILED,
}


class SeegenAdapter:
    """Adapter for Seegen.ai's job-based image generation API."""

    def __init__(self, api_key: str | None) -> None:
        # Stored but not validated at construction — keys are checked lazily
        # in the public methods so the app can still boot if the key is
        # missing from .env (the model just won't work until configured).
        self._api_key = api_key

    # ------------------------------------------------------------------
    # AsyncProviderAdapter Protocol
    # ------------------------------------------------------------------

    def submit_async(self, model_id: str, inputs: GenerationInput) -> str:
        """Submit a generation job and return Seegen's taskId.

        Returns immediately — does not wait for completion. Raises if the
        submission itself fails (auth, quota, validation); transient
        polling failures are handled by `poll_status`.
        """
        self._require_key()
        if not inputs.text:
            raise ValueError("Seegen requires a text prompt.")

        # Convention: model_id is `seegen-<model>`, e.g. `seegen-gpt-image-2`.
        # The suffix maps directly to Seegen's `model` field.
        model_name = model_id.removeprefix("seegen-") or "gpt-image-2"

        adapter_inputs: dict[str, Any] = {
            "prompt": inputs.text,
            "quality": _DEFAULT_QUALITY,
            "resolution": _DEFAULT_RESOLUTION,
            "aspectRatio": _DEFAULT_ASPECT_RATIO,
            "outputFormat": _DEFAULT_OUTPUT_FORMAT,
        }
        # Sprint 4A.4 — passing `urls` switches Seegen into image-to-image
        # ("edit") mode. Per the docs they accept 1–10 image URLs. We cap
        # to the same range here so we surface a clear error rather than
        # punting it to the API.
        if inputs.image_urls:
            adapter_inputs["urls"] = inputs.image_urls[:10]

        body = {"model": model_name, "inputs": adapter_inputs}
        return self._submit(body)

    def poll_status(self, model_id: str, job_id: str) -> JobStatus:
        """Check the job's current state. Non-blocking — returns immediately.

        On COMPLETED, builds a GenerationOutput pointing at the first image
        URL Seegen produced. On FAILED, captures the error message. On
        anything else (PENDING/PROCESSING), returns JobState.PROCESSING and
        leaves the caller to re-enqueue itself.
        """
        self._require_key()
        del model_id  # not needed — Seegen's job id is globally unique

        query = urllib.parse.urlencode({"taskId": job_id})
        url = f"{_BASE_URL}{_QUERY_PATH}?{query}"
        request = urllib.request.Request(
            url,
            headers=self._auth_headers(),
            method="GET",
        )
        data = self._read_json(request)
        raw_status = data.get("status", "")
        state = _SEEGEN_TO_JOB_STATE.get(raw_status, JobState.PROCESSING)

        if state is JobState.DONE:
            return JobStatus(state=state, output=_extract_output(data, job_id))
        if state is JobState.FAILED:
            err = data.get("error") or "Seegen reported FAILED with no error message."
            return JobStatus(state=state, error=f"Seegen task {job_id} failed: {err}")
        return JobStatus(state=state)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_key(self) -> None:
        if not self._api_key:
            raise RuntimeError(
                "Seegen API key is not configured. Set SEEGEN_API_KEY in apps/api/.env."
            )

    def _submit(self, body: Mapping[str, Any]) -> str:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            _BASE_URL + _CREATE_PATH,
            data=payload,
            headers=self._auth_headers() | {"Content-Type": "application/json"},
            method="POST",
        )
        data = self._read_json(request)
        task_id = data.get("taskId")
        if not isinstance(task_id, str) or not task_id:
            raise RuntimeError(f"Seegen createTask returned no taskId: {data!r}")
        return task_id

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _read_json(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
                raw = response.read()
        except urllib.error.HTTPError as exc:
            # Surface Seegen's error body verbatim — its messages are usually
            # informative (quota, validation, etc.) and the ErrorCard parser
            # on the frontend can map common codes to friendlier copy.
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Seegen HTTP {exc.code}: {body[:500]}"
            ) from exc

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Seegen returned non-JSON: {raw[:200]!r}") from exc

        if not isinstance(parsed, dict):
            raise RuntimeError(f"Seegen returned non-object JSON: {parsed!r}")
        return parsed


def _extract_output(data: dict[str, Any], job_id: str) -> GenerationOutput:
    """Pull the first image URL out of a COMPLETED queryTask response.

    Defensive — Seegen's payload shape is documented but we'd rather raise
    a clear error than silently produce a row with no URL if the shape
    changes upstream.
    """
    output = data.get("output")
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, dict):
            url_val = first.get("url")
            if isinstance(url_val, str):
                return GenerationOutput(output_type=OutputType.IMAGE, url=url_val)
    raise RuntimeError(
        f"Seegen task {job_id} completed but returned no usable URL: {data!r}"
    )
