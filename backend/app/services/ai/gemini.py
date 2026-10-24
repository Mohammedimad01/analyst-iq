"""The only module that talks to Gemini. Uses Google's `google-genai` SDK; model and key come from settings.

Failure policy: every provider problem becomes an AiError with a stable code. Timeouts, network errors and 5xx
get exactly one retry; auth errors, bad requests and quota/rate limits (429) are never retried.
"""

import logging
import time
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.core.config import get_settings

log = logging.getLogger("analyst_iq.ai")
RETRY_DELAY_SECONDS = 2.0


class AiError(Exception):
    def __init__(self, code: str, message: str, http_status: int, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.http_status, self.retryable = code, message, http_status, retryable


class JsonModel(Protocol):
    model: str

    def generate_json(self, system: str, prompt: str, schema: type[BaseModel]) -> str: ...


class GoogleGeminiClient:
    def __init__(self, api_key: str, model: str, timeout_seconds: float):
        from google import genai
        from google.genai import types

        self.model = model
        self._types = types
        # attempts=1 turns SDK retries off: retries are decided here, once, so quota is never burned in a loop.
        self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=int(timeout_seconds * 1000), retry_options=types.HttpRetryOptions(attempts=1)))

    def generate_json(self, system: str, prompt: str, schema: type[BaseModel]) -> str:
        from google.genai import errors

        config = self._types.GenerateContentConfig(
            system_instruction=system, response_mime_type="application/json", response_schema=schema,
            temperature=0.2, max_output_tokens=8192)
        try:
            response = self._client.models.generate_content(model=self.model, contents=prompt, config=config)
        except errors.ClientError as exc:
            if exc.code == 429:
                raise AiError("ai_rate_limited", "Gemini rate limit or free-tier quota reached. Try again later.", 429)
            if exc.code in (401, 403):
                raise AiError("ai_auth_failed", "Gemini rejected the API key. Check GEMINI_API_KEY.", 503)
            if exc.code == 404:
                # Google's message names the replacement model when one is retired; it contains no secrets.
                hint = f" Provider says: {str(exc.message)[:200]}" if exc.message else ""
                raise AiError("ai_model_not_found", f"Model '{self.model}' is not available to this API key. "
                                                    f"Check GEMINI_MODEL.{hint}", 503)
            raise AiError("ai_bad_request", f"Gemini rejected the request ({exc.code}).", 502)
        except errors.ServerError as exc:
            raise AiError("ai_provider_error", f"Gemini had a server error ({exc.code}).", 502, retryable=True)
        except httpx.TimeoutException:
            raise AiError("ai_timeout", "Gemini did not respond in time.", 504, retryable=True)
        except httpx.HTTPError:
            raise AiError("ai_network_error", "Could not reach Gemini.", 502, retryable=True)
        text = response.text if response is not None else None
        if not text or not text.strip():
            raise AiError("ai_empty_response", "Gemini returned an empty response (it may have been blocked).", 502)
        return text


def get_ai_client() -> JsonModel:
    settings = get_settings()
    if not settings.gemini_configured:
        raise AiError("ai_not_configured", "AI insights are not configured. Set GEMINI_API_KEY and GEMINI_MODEL "
                                           "in .env; dashboards and anomaly detection work without them.", 503)
    return GoogleGeminiClient(settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds)


def call_with_retry(client: JsonModel, system: str, prompt: str, schema: type[BaseModel]) -> str:
    try:
        return client.generate_json(system, prompt, schema)
    except AiError as exc:
        if not exc.retryable:
            raise
        log.warning("gemini call failed (%s); retrying once", exc.code)
        time.sleep(RETRY_DELAY_SECONDS)
        return client.generate_json(system, prompt, schema)
