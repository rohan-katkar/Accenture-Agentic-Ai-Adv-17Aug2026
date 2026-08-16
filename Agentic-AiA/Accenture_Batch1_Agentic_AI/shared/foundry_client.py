"""
shared/foundry_client.py
========================
One model-access seam for the entire programme.

DESIGN RULE
-----------
No lab ever constructs an SDK client. Labs call get_chat_client() and
get_embedder(). That indirection is not academic tidiness - it is the reason a
breaking change in a preview SDK, an expired key, or an air-gapped training room
costs you one file instead of fifteen labs.

THREE BACKENDS, chosen automatically
------------------------------------
  OFFLINE  - LAB_OFFLINE_MODE=true. Deterministic stub. No network. Every lab
             still runs end to end. Use for dry-runs and dead-key mornings.
  PATH A   - Azure OpenAI endpoint through the `openai` SDK. PRIMARY teaching
             path. Stable, versioned by an explicit api-version string.
  PATH B   - Azure AI Foundry project-scoped SDK (azure-ai-projects), enabled
             only when USE_FOUNDRY_PROJECT_SDK=true.

!! ACCURACY NOTE ON PATH B - READ BEFORE TEACHING IT !!
-------------------------------------------------------
The azure-ai-projects package has changed its client surface across its preview
line and its GA release. The accessor used to obtain a chat client has appeared
in more than one shape. This module therefore *probes* for a working accessor
rather than hard-coding one, and raises an explicit, actionable error if none is
found. Do not present any single Path B call signature to a class as settled
fact without first re-verifying it against current Microsoft Learn documentation
and running 00_Program/verify_environment.py on the delivery machine.
Path A is the path to teach. Path B is the path to demonstrate and to flag.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from typing import Any, Callable, Protocol, Sequence

from shared.config import settings
from shared.telemetry import get_logger, log_event

log = get_logger(__name__)


# ==========================================================================
# 1. Static token credential adapter
# ==========================================================================
# The Azure SDKs authenticate through a *credential object*, not a raw string.
# In production you use DefaultAzureCredential (managed identity, workload
# identity, az login). In a training room you frequently have only a key or a
# pre-issued token. The adapter below satisfies the TokenCredential protocol
# with a fixed token, which lets a key-based classroom exercise the exact same
# code path as a production identity-based deployment.
#
# PRODUCTION GUIDANCE - say this out loud in class:
#   This adapter is a *teaching and break-glass* construct. Shipping it to
#   production means a non-rotating, non-expiring secret in your process memory.
#   Production uses DefaultAzureCredential / ManagedIdentityCredential.

try:
    from azure.core.credentials import AccessToken  # type: ignore

    _AZURE_CORE = True
except ImportError:  # pragma: no cover - azure-core is optional for offline runs
    _AZURE_CORE = False

    class AccessToken:  # type: ignore[no-redef]
        """Minimal stand-in so the module imports without azure-core installed."""

        def __init__(self, token: str, expires_on: int) -> None:
            self.token = token
            self.expires_on = expires_on


class StaticTokenCredential:
    """Satisfies the azure.core TokenCredential protocol with a fixed token.

    The SDK calls get_token(*scopes) and expects an object exposing `.token`
    and `.expires_on` (POSIX seconds). That is the whole contract.
    """

    def __init__(self, token: str, ttl_seconds: int = 3600) -> None:
        if not token:
            raise ValueError("StaticTokenCredential requires a non-empty token.")
        self._token = token
        self._ttl = ttl_seconds

    def get_token(self, *scopes: str, **kwargs: Any) -> AccessToken:  # noqa: ARG002
        log_event(log, "credential_issued", adapter="StaticTokenCredential",
                  scopes=list(scopes), ttl_seconds=self._ttl)
        return AccessToken(self._token, int(time.time()) + self._ttl)

    def close(self) -> None:  # SDKs may call this
        return None


def build_credential() -> Any:
    """Return the credential this environment should use.

    Order: explicit static token -> DefaultAzureCredential -> None (key auth).
    """
    if settings.azure_openai_api_key and settings.azure_openai_api_key.startswith("Bearer "):
        return StaticTokenCredential(settings.azure_openai_api_key.removeprefix("Bearer "))
    try:
        from azure.identity import DefaultAzureCredential  # type: ignore

        return DefaultAzureCredential(exclude_interactive_browser_credential=False)
    except ImportError:
        return None


# ==========================================================================
# 2. Chat client interface
# ==========================================================================

class ChatClient(Protocol):
    backend_name: str

    def complete(self, system: str, user: str, *, temperature: float = 0.0,
                 max_tokens: int = 800) -> str: ...


class _CompletionMixin:
    """Adds JSON-mode helpers shared by every backend."""

    def complete_json(self, system: str, user: str, *, temperature: float = 0.0,
                      max_tokens: int = 800) -> dict:
        """Ask for JSON, then parse defensively.

        Models wrap JSON in markdown fences even when told not to. Stripping the
        fence in one place beats debugging it in five labs. Day 3 replaces this
        with Pydantic validation - parsing is not the same as trusting.
        """
        hardened = (
            f"{system}\n\n"
            "Respond with a single valid JSON object and nothing else. "
            "No prose, no explanation, no markdown code fences."
        )
        raw = self.complete(hardened, user, temperature=temperature, max_tokens=max_tokens)  # type: ignore[attr-defined]
        return parse_json_loose(raw)


def parse_json_loose(raw: str) -> dict:
    """Extract the first JSON object from a model response."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Model did not return parseable JSON. First 300 chars: {raw[:300]!r}")


# --------------------------------------------------------------------------
# 2a. OFFLINE backend
# --------------------------------------------------------------------------

class OfflineChatClient(_CompletionMixin):
    """Deterministic stub. Never touches the network.

    It is keyword-driven, not intelligent. Its only job is to keep the *graph
    plumbing* teachable when the model endpoint is unavailable. Any lab whose
    learning objective is model behaviour must be run against Path A.

    DESIGN DETAIL THAT MATTERS (Day 2 Lab 4):
        The stub quotes a VERBATIM sentence from the user prompt rather than
        emitting a canned paraphrase. That is not cosmetic. Lab 4 enforces
        grounding by checking the model's citation is a literal substring of the
        retrieved document; a stub that paraphrases would fail that check on
        every case and make the lab unrunnable offline. A stand-in that cannot
        satisfy the controls under test is not a stand-in.

        It matches keywords ONLY in the user text, never in the system prompt.
        Matching the system prompt would fire D03 on every call, because the
        prompt itself lists "Damage Claim" among the legal codes.
    """

    backend_name = "offline-stub"

    # code -> (category, keywords)
    _RULES = [
        ("D03", "Damage Claim", ("crushed", "damaged", "damage", "broken", "unusable")),
        ("D02", "Freight Claim", ("freight", "shipping charge", "handling charge")),
        ("D01", "Pricing Issue", ("contracted price", "unit price", "price differs", "pricing")),
        ("D04", "Tax Difference", ("tax exempt", "sales tax", "exemption")),
        ("D05", "Discount Taken", ("early payment discount", "discount taken", "payment terms")),
    ]

    def complete(self, system: str, user: str, *, temperature: float = 0.0,
                 max_tokens: int = 800) -> str:  # noqa: ARG002
        log_event(log, "offline_completion", chars_in=len(user))

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", user) if s.strip()]
        lowered = user.lower()

        for code, category, keywords in self._RULES:
            hit = next((k for k in keywords if k in lowered), None)
            if not hit:
                continue
            quote = next((s for s in sentences if hit in s.lower()), "")
            quote = " ".join(quote.split())[:200]
            if not quote:
                continue
            amount = None
            money = re.search(r"(?:USD\s*)?([\d,]+\.\d{2})", quote)
            if money:
                try:
                    amount = float(money.group(1).replace(",", ""))
                except ValueError:
                    amount = None
            return json.dumps({
                "reason_code": code, "category": category,
                "confidence": 0.85, "evidence": quote,
                "deducted_amount_usd": amount,
            })

        if "json" in system.lower() or "json" in lowered:
            return json.dumps({
                "reason_code": "UNKNOWN", "category": "Unclassified",
                "confidence": 0.0, "evidence": "", "deducted_amount_usd": None,
            })
        return ("OFFLINE STUB RESPONSE - no live model configured. "
                "Set LAB_OFFLINE_MODE=false to use Azure.")


class OfflineEmbedder:
    """Hashed bag-of-words embedder. Deterministic, offline, zero downloads.

    HONESTY LABEL - state this to the class:
        This is LEXICAL similarity, not SEMANTIC similarity. "invoice was short
        paid" and "customer underpaid the bill" share no tokens and will NOT
        retrieve each other here, though a real embedding model would place them
        close together. Use this only to prove the *pipeline* works. Every
        retrieval-quality claim in Day 2 must be demonstrated against Path A.
    """

    dim = 256
    backend_name = "offline-hashed-bow"

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(token.encode()).hexdigest()[:8], 16)
            vec[h % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


# --------------------------------------------------------------------------
# 2b. PATH A - Azure OpenAI through the `openai` SDK
# --------------------------------------------------------------------------

class AzureOpenAIChatClient(_CompletionMixin):
    """Primary teaching path.

    `model=` takes the *deployment name*, not the model family name. That single
    fact accounts for a large share of first-day support tickets: a deployment
    called `gpt4o-prod` must be passed as `gpt4o-prod`, not `gpt-4o`.
    """

    backend_name = "azure-openai"

    def __init__(self) -> None:
        from openai import AzureOpenAI  # imported lazily so offline runs need no SDK

        self._deployment = settings.chat_deployment
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    def complete(self, system: str, user: str, *, temperature: float = 0.0,
                 max_tokens: int = 800) -> str:
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = getattr(response, "usage", None)
        log_event(
            log, "chat_completion",
            deployment=self._deployment,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
        )
        return (response.choices[0].message.content or "").strip()


class AzureOpenAIEmbedder:
    backend_name = "azure-openai-embeddings"

    def __init__(self) -> None:
        from openai import AzureOpenAI

        self._deployment = settings.embedding_deployment
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    def __call__(self, texts: Sequence[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._deployment, input=list(texts))
        log_event(log, "embeddings_created", deployment=self._deployment, count=len(texts))
        return [item.embedding for item in response.data]


# --------------------------------------------------------------------------
# 2c. PATH B - Azure AI Foundry project SDK (probed, not assumed)
# --------------------------------------------------------------------------

class FoundryProjectChatClient(_CompletionMixin):
    """Project-scoped access via azure-ai-projects.

    WHY A PROJECT CLIENT AT ALL, when Path A already works?
        A project endpoint resolves connections, deployments and (depending on
        configuration) governance policy centrally. Application code stops
        carrying per-resource endpoints. That is the enterprise argument.

    WHY THIS CLASS PROBES INSTEAD OF CALLING A FIXED METHOD:
        The accessor for obtaining a chat client from AIProjectClient has not
        been stable across the package's preview line. Rather than hard-code a
        call that may be wrong on your installed version, we try the known
        shapes in order and fail loudly with the installed version number.
    """

    backend_name = "azure-ai-foundry-project"

    def __init__(self) -> None:
        from azure.ai.projects import AIProjectClient  # type: ignore

        credential = build_credential()
        if credential is None:
            raise RuntimeError(
                "Path B needs azure-identity installed (or a Bearer token in "
                "AZURE_OPENAI_API_KEY for StaticTokenCredential)."
            )

        self._project = AIProjectClient(
            endpoint=settings.project_endpoint,
            credential=credential,
        )
        self._deployment = settings.chat_deployment
        self._mode, self._inner = self._resolve_inner_client()
        log_event(log, "foundry_path_b_resolved", accessor=self._mode)

    def _resolve_inner_client(self) -> tuple[str, Any]:
        """Try known accessor shapes. Order = most recent first."""
        attempts: list[tuple[str, Callable[[], Any]]] = [
            ("get_openai_client",
             lambda: self._project.get_openai_client(  # type: ignore[attr-defined]
                 api_version=settings.azure_openai_api_version)),
            ("inference.get_chat_completions_client",
             lambda: self._project.inference.get_chat_completions_client()),  # type: ignore[attr-defined]
        ]
        errors: list[str] = []
        for name, factory in attempts:
            try:
                return name, factory()
            except Exception as exc:  # noqa: BLE001 - probing is the point
                errors.append(f"{name}: {type(exc).__name__}: {exc}")

        installed = "unknown"
        try:
            from importlib.metadata import version

            installed = version("azure-ai-projects")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(
            "Could not obtain a chat client from AIProjectClient.\n"
            f"  installed azure-ai-projects == {installed}\n"
            "  attempts:\n    " + "\n    ".join(errors) + "\n"
            "ACTION: check the current accessor in Microsoft Learn for your "
            "installed version, add it to _resolve_inner_client(), or set "
            "USE_FOUNDRY_PROJECT_SDK=false to fall back to Path A."
        )

    def complete(self, system: str, user: str, *, temperature: float = 0.0,
                 max_tokens: int = 800) -> str:
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        if self._mode == "get_openai_client":
            resp = self._inner.chat.completions.create(
                model=self._deployment, messages=messages,
                temperature=temperature, max_tokens=max_tokens)
            return (resp.choices[0].message.content or "").strip()
        # azure-ai-inference style client
        resp = self._inner.complete(
            messages=messages, model=self._deployment,
            temperature=temperature, max_tokens=max_tokens)
        return (resp.choices[0].message.content or "").strip()


# ==========================================================================
# 3. Factories - the only functions labs import
# ==========================================================================

_chat_singleton: ChatClient | None = None
_embed_singleton: Callable[[Sequence[str]], list[list[float]]] | None = None


def get_chat_client(*, force_reload: bool = False) -> ChatClient:
    """Return the best available chat client for this environment."""
    global _chat_singleton
    if _chat_singleton is not None and not force_reload:
        return _chat_singleton

    if settings.offline_mode:
        _chat_singleton = OfflineChatClient()
    elif settings.path_b_ready:
        try:
            _chat_singleton = FoundryProjectChatClient()
        except Exception as exc:  # noqa: BLE001
            log_event(log, "path_b_failed_falling_back", error=str(exc))
            _chat_singleton = AzureOpenAIChatClient() if settings.path_a_ready else OfflineChatClient()
    elif settings.path_a_ready:
        _chat_singleton = AzureOpenAIChatClient()
    else:
        log_event(log, "no_credentials_using_offline_stub")
        _chat_singleton = OfflineChatClient()

    log_event(log, "chat_client_ready", backend=_chat_singleton.backend_name)
    return _chat_singleton


def get_embedder(*, force_reload: bool = False) -> Callable[[Sequence[str]], list[list[float]]]:
    """Return an embedding function: list[str] -> list[list[float]]."""
    global _embed_singleton
    if _embed_singleton is not None and not force_reload:
        return _embed_singleton

    if settings.offline_mode or not settings.path_a_ready:
        _embed_singleton = OfflineEmbedder()
    else:
        try:
            _embed_singleton = AzureOpenAIEmbedder()
        except Exception as exc:  # noqa: BLE001
            log_event(log, "embedder_fallback", error=str(exc))
            _embed_singleton = OfflineEmbedder()

    log_event(log, "embedder_ready", backend=getattr(_embed_singleton, "backend_name", "?"))
    return _embed_singleton


def active_backend_summary() -> str:
    chat = get_chat_client()
    emb = get_embedder()
    return (f"chat backend = {chat.backend_name}\n"
            f"embed backend = {getattr(emb, 'backend_name', '?')}")
