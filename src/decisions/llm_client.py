"""
OpenRouter (OpenAI-compatible) wrapper for structured agent decisions.

We use the ``openai`` SDK pointed at ``https://openrouter.ai/api/v1``. Model
names follow OpenRouter's ``provider/model-version`` convention
(e.g. ``anthropic/claude-haiku-4.5``).

Responsibilities:
  - Forced tool-use for structured decision output.
  - Retry with exponential backoff on transient errors.
  - In-process response cache keyed on hash of (model, system_prompt,
    user_message, tool_schema). Optional disk persistence for replay.
  - Per-call cost: when OpenRouter returns ``usage.cost`` (we ask via the
    ``usage.include`` extra body field), we use that as ground truth; otherwise
    we estimate from a token-price table.
  - Aggregate ``CallSummary`` printed at end of run.

What we lost vs. the native Anthropic client:
  - Anthropic prompt caching via ``cache_control``. OpenRouter passes this
    through for some models but it doesn't round-trip cleanly via the OpenAI
    SDK content-parts shape. Revisit as a Day-5 cost optimization.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models, base URL, pricing
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = os.environ.get(
    "AGENT_BANKRUN_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
)

# OpenRouter model IDs follow the pattern <provider>/<model>-<version>.
# These defaults are conservative — override via env vars if OpenRouter exposes
# different canonical names for the Claude 4.x line.
DEFAULT_HAIKU_MODEL = os.environ.get(
    "AGENT_BANKRUN_HAIKU_MODEL", "anthropic/claude-haiku-4.5"
)
DEFAULT_SONNET_MODEL = os.environ.get(
    "AGENT_BANKRUN_SONNET_MODEL", "anthropic/claude-sonnet-4.5"
)

# Per-million-token prices in USD (input, output). These are our local fallback
# estimates; OpenRouter reports authoritative ``usage.cost`` when we ask for it.
DEFAULT_PRICING_USD_PER_MTOK: Dict[str, Tuple[float, float]] = {
    "anthropic/claude-haiku-4.5":  (1.00, 5.00),
    "anthropic/claude-sonnet-4.5": (3.00, 15.00),
    "anthropic/claude-sonnet-4.6": (3.00, 15.00),
    "anthropic/claude-opus-4.7":   (15.00, 75.00),
}


# ---------------------------------------------------------------------------
# Decision tool schema (OpenAI function-tool shape)
# ---------------------------------------------------------------------------

DECISION_TOOL_NAME = "record_financial_decision"

DECISION_TOOL_SCHEMA: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": DECISION_TOOL_NAME,
        "description": (
            "Record your financial decision after reasoning through your situation. "
            "Reasoning comes first — think aloud about your cost function and the "
            "asymmetry of being wrong before committing to an action."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reasoning": {
                    "type": "string",
                    "description": (
                        "Your reasoning in your own voice (3-6 sentences). Reference "
                        "the specific costs from your cost function and the asymmetry "
                        "between being wrong by acting vs. not acting. Should sound "
                        "like this specific persona, not generic financial advice."
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": ["hold", "partial_withdraw", "full_withdraw", "increase_deposit"],
                    "description": (
                        "The action to take. 'hold' = do nothing. "
                        "'partial_withdraw' = withdraw a fraction of your deposit at "
                        "the bank in focus. 'full_withdraw' = withdraw everything. "
                        "'increase_deposit' = add more to this bank."
                    ),
                },
                "amount_fraction": {
                    "type": "number",
                    "description": (
                        "For 'partial_withdraw' or 'increase_deposit': the fraction "
                        "of the current deposit to act on (0.0–1.0). For 'hold' use "
                        "0.0; for 'full_withdraw' use 1.0."
                    ),
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "confidence": {
                    "type": "number",
                    "description": "Your confidence in this decision (0.0–1.0).",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["reasoning", "action", "amount_fraction", "confidence"],
        },
    },
}


# ---------------------------------------------------------------------------
# Result / call-record types
# ---------------------------------------------------------------------------


@dataclass
class LLMCallResult:
    """Everything we record from a single LLM call."""

    tool_input: Dict[str, Any]   # the structured decision the model returned
    model: str
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    cost_usd: float
    cost_source: str             # "openrouter_reported" | "estimated_from_tokens" | "cache"
    cache_hit: bool              # in-process cache hit (response replayed verbatim)
    raw_response: Dict[str, Any] # the full chat-completion response, lightly normalized


@dataclass
class CallSummary:
    total_calls: int = 0
    cache_hits: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_prompt_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------


class LLMClient:
    """OpenRouter chat-completions client tuned for our structured decisions."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = OPENROUTER_BASE_URL,
        cache_dir: Optional[Path] = None,
        max_retries: int = 4,
        initial_backoff_seconds: float = 1.0,
        pricing: Optional[Dict[str, Tuple[float, float]]] = None,
        http_referer: Optional[str] = None,
        x_title: Optional[str] = None,
        request_timeout_seconds: float = 60.0,
    ):
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "openai package not installed. Run `pip install openai`."
            ) from exc

        resolved_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY not set. Put it in .env or pass api_key= explicitly."
            )

        # Optional cosmetic headers used by OpenRouter for app rankings.
        default_headers: Dict[str, str] = {}
        referer = http_referer or os.environ.get("AGENT_BANKRUN_HTTP_REFERER")
        title = x_title or os.environ.get("AGENT_BANKRUN_X_TITLE", "agent-bankrun")
        if referer:
            default_headers["HTTP-Referer"] = referer
        if title:
            default_headers["X-Title"] = title

        # Explicit per-request timeout. The SDK default is 600s, so a single hung
        # call could freeze a run (and a live demo) for ten minutes before retrying.
        # A tight timeout fails fast → our retry loop (or the engine's hold-fallback)
        # keeps the simulation moving.
        self._client = OpenAI(
            api_key=resolved_key,
            base_url=base_url,
            default_headers=default_headers or None,
            timeout=request_timeout_seconds,
        )
        self._max_retries = max_retries
        self._initial_backoff = initial_backoff_seconds
        self._pricing = pricing or DEFAULT_PRICING_USD_PER_MTOK

        self._cache: Dict[str, LLMCallResult] = {}
        self._cache_dir: Optional[Path] = cache_dir
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_cache_from_disk()

        self._summary = CallSummary()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(
        self,
        *,
        system_prompt: str,
        user_message: str,
        model: str,
        max_tokens: int = 1024,
        tool_schema: Dict[str, Any] = DECISION_TOOL_SCHEMA,
        force_tool: bool = True,
        cache_system_prompt: bool = True,  # accepted for compatibility; see module docstring
        tool_validator=None,  # callable(dict)->dict; None → _validate_decision_tool_input
    ) -> LLMCallResult:
        """Make a structured decision call. Returns an ``LLMCallResult``."""
        del cache_system_prompt  # accepted-but-unused; OpenRouter prompt caching is a TODO

        cache_key = _hash_call(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            tool_schema=tool_schema,
        )

        cached = self._cache.get(cache_key)
        if cached is not None:
            replayed = LLMCallResult(
                tool_input=cached.tool_input,
                model=cached.model,
                prompt_tokens=0,
                completion_tokens=0,
                cached_prompt_tokens=0,
                cost_usd=0.0,
                cost_source="cache",
                cache_hit=True,
                raw_response=cached.raw_response,
            )
            self._record_summary(replayed)
            return replayed

        result = self._call_with_retry(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=max_tokens,
            tool_schema=tool_schema,
            force_tool=force_tool,
            tool_validator=tool_validator,
        )

        self._cache[cache_key] = result
        if self._cache_dir is not None:
            self._persist_cache_entry(cache_key, result)
        self._record_summary(result)
        return result

    def summary(self) -> CallSummary:
        with self._lock:
            return CallSummary(
                total_calls=self._summary.total_calls,
                cache_hits=self._summary.cache_hits,
                total_prompt_tokens=self._summary.total_prompt_tokens,
                total_completion_tokens=self._summary.total_completion_tokens,
                total_cached_prompt_tokens=self._summary.total_cached_prompt_tokens,
                total_cost_usd=self._summary.total_cost_usd,
                by_model=dict(self._summary.by_model),
            )

    def format_cost_summary(self) -> str:
        s = self.summary()
        lines = [
            "LLM call summary:",
            f"  total calls:        {s.total_calls}",
            f"  cache hits:         {s.cache_hits}",
            f"  prompt tokens:      {s.total_prompt_tokens:,}",
            f"  cached input:       {s.total_cached_prompt_tokens:,}",
            f"  completion tokens:  {s.total_completion_tokens:,}",
            f"  total cost USD:     ${s.total_cost_usd:.4f}",
        ]
        if s.by_model:
            lines.append("  calls by model:")
            for model, count in sorted(s.by_model.items()):
                lines.append(f"    {model}: {count}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        tool_schema: Dict[str, Any],
        force_tool: bool,
        tool_validator=None,
    ) -> LLMCallResult:
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "tools": [tool_schema],
            # Ask OpenRouter to include authoritative cost info on the response.
            "extra_body": {"usage": {"include": True}},
        }
        if force_tool:
            kwargs["tool_choice"] = {
                "type": "function",
                "function": {"name": tool_schema["function"]["name"]},
            }

        last_err: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.chat.completions.create(**kwargs)
                return self._extract_result(
                    response,
                    model=model,
                    expected_tool_name=tool_schema["function"]["name"],
                    tool_validator=tool_validator,
                )
            except ValueError as exc:
                # Malformed tool call (missing fields, bad JSON, wrong tool name).
                # Retry immediately — no backoff needed, this is a model quality
                # issue not a rate limit. Haiku occasionally drops required fields.
                last_err = exc
                if attempt == self._max_retries:
                    break
                logger.warning(
                    "Malformed tool call (attempt %d/%d): %s — retrying",
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001
                if not _is_retriable(exc):
                    raise
                last_err = exc
                if attempt == self._max_retries:
                    break
                backoff = self._initial_backoff * (2 ** attempt) * (0.75 + 0.5 * random.random())
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    self._max_retries,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
        assert last_err is not None
        raise last_err

    def _extract_result(self, response: Any, *, model: str, expected_tool_name: str, tool_validator=None) -> LLMCallResult:
        if not response.choices:
            raise ValueError(f"No choices in response: {response!r}")
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            raise ValueError(
                f"Model did not produce a tool call. finish_reason="
                f"{response.choices[0].finish_reason!r} content={getattr(message, 'content', None)!r}"
            )
        tool_call = tool_calls[0]
        if tool_call.function.name != expected_tool_name:
            raise ValueError(
                f"Unexpected tool name: got {tool_call.function.name!r}, expected {expected_tool_name!r}"
            )
        try:
            tool_input = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Tool arguments not valid JSON: {tool_call.function.arguments!r}"
            ) from exc

        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cached_prompt_tokens = 0
        prompt_details = getattr(usage, "prompt_tokens_details", None)
        if prompt_details is not None:
            cached_prompt_tokens = int(getattr(prompt_details, "cached_tokens", 0) or 0)

        # Authoritative cost from OpenRouter when available; fall back to estimate.
        reported_cost = _pluck_reported_cost(usage, response)
        if reported_cost is not None:
            cost = reported_cost
            cost_source = "openrouter_reported"
        else:
            cost = self._compute_cost_from_tokens(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_prompt_tokens=cached_prompt_tokens,
            )
            cost_source = "estimated_from_tokens"

        raw = {
            "id": getattr(response, "id", None),
            "model": getattr(response, "model", model),
            "finish_reason": response.choices[0].finish_reason,
            "tool_call": {
                "name": tool_call.function.name,
                "arguments": tool_call.function.arguments,
            },
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cached_prompt_tokens": cached_prompt_tokens,
                "reported_cost_usd": reported_cost,
            },
        }

        validator = tool_validator if tool_validator is not None else _validate_decision_tool_input
        return LLMCallResult(
            tool_input=validator(tool_input),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
            cost_usd=cost,
            cost_source=cost_source,
            cache_hit=False,
            raw_response=raw,
        )

    def _compute_cost_from_tokens(
        self,
        *,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int,
    ) -> float:
        in_price, out_price = self._pricing.get(model, (3.0, 15.0))
        # Cached input tokens billed at ~10% of input price (Anthropic convention).
        billed_input = max(0, prompt_tokens - cached_prompt_tokens)
        cost = (
            (billed_input * in_price)
            + (cached_prompt_tokens * in_price * 0.10)
            + (completion_tokens * out_price)
        ) / 1_000_000.0
        return cost

    def _record_summary(self, result: LLMCallResult) -> None:
        with self._lock:
            self._summary.total_calls += 1
            if result.cache_hit:
                self._summary.cache_hits += 1
            self._summary.total_prompt_tokens += result.prompt_tokens
            self._summary.total_completion_tokens += result.completion_tokens
            self._summary.total_cached_prompt_tokens += result.cached_prompt_tokens
            self._summary.total_cost_usd += result.cost_usd
            self._summary.by_model[result.model] = self._summary.by_model.get(result.model, 0) + 1

    # ---- Disk cache (optional) --------------------------------------

    def _load_cache_from_disk(self) -> None:
        if self._cache_dir is None:
            return
        for path in self._cache_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                key = path.stem
                self._cache[key] = LLMCallResult(
                    tool_input=payload["tool_input"],
                    model=payload["model"],
                    prompt_tokens=0,
                    completion_tokens=0,
                    cached_prompt_tokens=0,
                    cost_usd=0.0,
                    cost_source="cache",
                    cache_hit=True,
                    raw_response=payload.get("raw_response", {}),
                )
            except (OSError, KeyError, json.JSONDecodeError) as exc:
                logger.warning("Could not load cache entry %s: %s", path, exc)

    def _persist_cache_entry(self, key: str, result: LLMCallResult) -> None:
        if self._cache_dir is None:
            return
        path = self._cache_dir / f"{key}.json"
        payload = {
            "tool_input": result.tool_input,
            "model": result.model,
            "raw_response": result.raw_response,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pluck_reported_cost(usage: Any, response: Any) -> Optional[float]:
    """OpenRouter sticks 'cost' on usage when extra_body usage.include=true is set.

    The openai SDK's Usage type allows extra fields (it inherits from BaseModel
    with extra='allow' on most versions), so getattr works. We also probe the
    raw response just in case.
    """
    if usage is None:
        return None
    cost = getattr(usage, "cost", None)
    if cost is not None:
        try:
            return float(cost)
        except (TypeError, ValueError):
            pass
    # Some response shapes put cost under usage.cost_details.upstream_inference_cost
    details = getattr(usage, "cost_details", None)
    if details is not None:
        upstream = getattr(details, "upstream_inference_cost", None)
        if upstream is not None:
            try:
                return float(upstream)
            except (TypeError, ValueError):
                pass
    # Fall back to a top-level field on the response object if present.
    cost = getattr(response, "cost", None)
    if cost is not None:
        try:
            return float(cost)
        except (TypeError, ValueError):
            pass
    return None


def _hash_call(*, model: str, system_prompt: str, user_message: str, tool_schema: Dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(system_prompt.encode("utf-8"))
    h.update(b"\x00")
    h.update(user_message.encode("utf-8"))
    h.update(b"\x00")
    h.update(json.dumps(tool_schema, sort_keys=True).encode("utf-8"))
    return h.hexdigest()


def _is_retriable(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    if any(s in name for s in ("ratelimit", "apiconnection", "apitimeout", "internalserver")):
        return True
    status = getattr(exc, "status_code", None)
    if status in (408, 409, 425, 429, 500, 502, 503, 504):
        return True
    # openai SDK puts status on response when the error has one
    response = getattr(exc, "response", None)
    if response is not None:
        rs = getattr(response, "status_code", None)
        if rs in (408, 409, 425, 429, 500, 502, 503, 504):
            return True
    return False


def _validate_decision_tool_input(tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Light validation so a malformed tool call surfaces immediately."""
    required = {"reasoning", "action", "amount_fraction", "confidence"}
    missing = required - set(tool_input.keys())
    if missing:
        raise ValueError(f"Decision tool input missing fields: {missing}")
    action = tool_input["action"]
    if action not in {"hold", "partial_withdraw", "full_withdraw", "increase_deposit"}:
        raise ValueError(f"Unknown action: {action!r}")
    af = float(tool_input["amount_fraction"])
    if not (0.0 <= af <= 1.0):
        raise ValueError(f"amount_fraction out of range: {af}")
    conf = float(tool_input["confidence"])
    if not (0.0 <= conf <= 1.0):
        raise ValueError(f"confidence out of range: {conf}")
    if action == "hold":
        tool_input["amount_fraction"] = 0.0
    elif action == "full_withdraw":
        tool_input["amount_fraction"] = 1.0
    return tool_input
