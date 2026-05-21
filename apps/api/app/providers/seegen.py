"""Seegen.ai provider — job-based image generation.

Seegen's API is **asynchronous**: POST `/jobs/createTask` returns a `taskId`
immediately, and the caller polls `/jobs/queryTask?taskId=...` until the
job reaches `COMPLETED` or `FAILED`.

For Sprint 3.5 we keep the ProviderAdapter Protocol synchronous: the Celery
worker already runs `generate()` off the request thread, so an adapter that
blocks while polling Seegen looks fine to the rest of the app. When Sprint 6
introduces Sjinn (also job-based) we'll extend the Protocol with explicit
`submit_async` + `poll_status` methods and a Celery task that re-enqueues
itself between polls, so a worker doesn't sit blocked for minutes.

API surface (https://seegen.ai/api-docs):
  POST /api/v1/jobs/createTask    → {"taskId": "..."}
  GET  /api/v1/jobs/queryTask?taskId=...
                                  → {"status": "PENDING|PROCESSING|COMPLETED|FAILED",
                                     "output": [{"url": "..."}], "error": ...}

Pricing is metered in Seegen's *own* credit system (not ours): 2k/medium is
35 of their credits. Failed tasks refund automatically on their side. Our
`cost_in_credits` field is independent — it represents what *we* charge our
user in *our* ledger.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any

from app.providers.types import GenerationInput, GenerationOutput, OutputType

_BASE_URL = "https://seegen.ai/api/v1"
_CREATE_PATH = "/jobs/createTask"
_QUERY_PATH = "/jobs/queryTask"

# Polling cadence. Seegen jobs typically finish in 15-45s. We poll a touch
# slower than Pollinations because we're hitting a real metered API.
_POLL_INTERVAL_SECONDS = 2.0
_POLL_TIMEOUT_SECONDS = 180  # hard ceiling — surface a timeout rather than hang forever
_HTTP_TIMEOUT_SECONDS = 30

# Seegen accepts these as inputs; we'll expose them as user-facing options in
# a later sprint once the dynamic form supports per-model parameters. For now,
# default to the cheapest tier — quality doesn't matter during development
# (15 of *their* credits per image at 1k/medium — 200 credits ≈ 13 test images).
_DEFAULT_QUALITY = "medium"
_DEFAULT_RESOLUTION = "1k"
_DEFAULT_ASPECT_RATIO = "1:1"
_DEFAULT_OUTPUT_FORMAT = "png"

_TERMINAL_OK = "COMPLETED"
_TERMINAL_FAIL = "FAILED"


class SeegenAdapter:
    """Adapter for Seegen.ai's job-based image generation API."""

    def __init__(self, api_key: str | None) -> None:
        # Stored but not validated at construction — keys are checked lazily
        # in `generate()` so the app can still boot if the key is missing
        # from .env (the model just won't work until configured).
        self._api_key = api_key

    def generate(self, model_id: str, inputs: GenerationInput) -> GenerationOutput:
        if not self._api_key:
            raise RuntimeError(
                "Seegen API key is not configured. Set SEEGEN_API_KEY in apps/api/.env."
            )
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

        body = {
            "model": model_name,
            "inputs": adapter_inputs,
        }

        task_id = self._submit(body)
        result_url = self._poll_until_done(task_id)
        return GenerationOutput(output_type=OutputType.IMAGE, url=result_url)

    # --- internals --------------------------------------------------------

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

    def _poll_until_done(self, task_id: str) -> str:
        deadline = time.monotonic() + _POLL_TIMEOUT_SECONDS
        query = urllib.parse.urlencode({"taskId": task_id})
        url = f"{_BASE_URL}{_QUERY_PATH}?{query}"

        while True:
            request = urllib.request.Request(
                url,
                headers=self._auth_headers(),
                method="GET",
            )
            data = self._read_json(request)
            status = data.get("status")

            if status == _TERMINAL_OK:
                output = data.get("output")
                if isinstance(output, list) and output:
                    first = output[0]
                    if isinstance(first, dict):
                        url_val = first.get("url")
                        if isinstance(url_val, str):
                            return url_val
                raise RuntimeError(
                    f"Seegen task {task_id} completed but returned no usable URL: {data!r}"
                )

            if status == _TERMINAL_FAIL:
                err = data.get("error") or "Seegen reported FAILED with no error message."
                raise RuntimeError(f"Seegen task {task_id} failed: {err}")

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Seegen task {task_id} did not finish within "
                    f"{_POLL_TIMEOUT_SECONDS}s (last status: {status})."
                )

            time.sleep(_POLL_INTERVAL_SECONDS)

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
