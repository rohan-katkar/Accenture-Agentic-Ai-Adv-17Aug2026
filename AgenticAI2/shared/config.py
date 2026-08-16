"""
shared/config.py
================
Single source of truth for lab configuration.

Every lab imports from here. No lab reads os.environ directly. That rule exists
so that when a key rotates, an endpoint moves, or the room goes offline, exactly
one file changes and all fifteen labs follow.

Loading order:
    1. Real process environment (wins - lets a trainer override per shell)
    2. .env at the repository root
    3. Built-in defaults below
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------
# Locate the repository root by walking up until we find the marker directory.
# --------------------------------------------------------------------------
def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "00_Program").is_dir():
            return parent
    return here.parent.parent


REPO_ROOT = _repo_root()

# --------------------------------------------------------------------------
# .env loading. python-dotenv is preferred; a tiny parser is the fallback so
# that a missing dependency never blocks Lab 1.
# --------------------------------------------------------------------------
def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path, override=False)
        return
    except ImportError:
        pass

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _abs_under_repo(path: str) -> str:
    """Resolve a relative path against the REPOSITORY ROOT, not the CWD.

    This is not pedantry. `CHROMA_PERSIST_DIR=./.chroma` interpreted against the
    working directory means Day 2 Lab 1 (run from solutions/) writes its
    collection somewhere the Streamlit app (run from the repo root) will never
    look - and the symptom is an empty collection with no error. Anchoring to the
    repo root makes the store location independent of where you launched from.
    """
    candidate = Path(path).expanduser()
    return str(candidate if candidate.is_absolute() else (REPO_ROOT / candidate).resolve())


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LabSettings:
    """Immutable snapshot of lab configuration."""

    # --- PATH A: Azure OpenAI / Foundry model endpoint (primary) ---
    azure_openai_endpoint: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
    )
    azure_openai_api_key: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_KEY", "")
    )
    azure_openai_api_version: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    )
    chat_deployment: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o-mini")
    )
    embedding_deployment: str = field(
        default_factory=lambda: os.getenv(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"
        )
    )

    # --- PATH B: Azure AI Foundry project SDK (optional) ---
    project_endpoint: str = field(
        default_factory=lambda: os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").rstrip("/")
    )
    use_project_sdk: bool = field(
        default_factory=lambda: _bool("USE_FOUNDRY_PROJECT_SDK", False)
    )

    # --- Runtime ---
    log_level: str = field(default_factory=lambda: os.getenv("LAB_LOG_LEVEL", "INFO"))
    offline_mode: bool = field(default_factory=lambda: _bool("LAB_OFFLINE_MODE", False))
    chroma_dir: str = field(
        default_factory=lambda: _abs_under_repo(
            os.getenv("CHROMA_PERSIST_DIR", ".chroma"))
    )

    # --- Business rules used from Day 2 onward (see Capstone spec) ---
    write_off_tolerance_usd: float = 10.00

    @property
    def path_a_ready(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_api_key)

    @property
    def path_b_ready(self) -> bool:
        return bool(self.project_endpoint and self.use_project_sdk)

    def describe(self) -> str:
        def mask(v: str) -> str:
            return f"{v[:4]}...{v[-4:]}" if len(v) > 12 else ("<set>" if v else "<empty>")

        return (
            f"offline_mode        = {self.offline_mode}\n"
            f"azure_endpoint      = {self.azure_openai_endpoint or '<empty>'}\n"
            f"azure_api_key       = {mask(self.azure_openai_api_key)}\n"
            f"api_version         = {self.azure_openai_api_version}\n"
            f"chat_deployment     = {self.chat_deployment}\n"
            f"embed_deployment    = {self.embedding_deployment}\n"
            f"project_endpoint    = {self.project_endpoint or '<empty>'}\n"
            f"use_project_sdk     = {self.use_project_sdk}\n"
            f"chroma_dir          = {self.chroma_dir}\n"
            f"write_off_tolerance = ${self.write_off_tolerance_usd:.2f}"
        )


settings = LabSettings()

SEED_DIR = REPO_ROOT / "shared" / "seed_data"
