"""Engine factory: picks an :class:`AsrEngine` by name or ``KITHORA_ENGINE``."""

from __future__ import annotations

import os
from collections.abc import Callable

from kithora.asr.base import AsrEngine
from kithora.asr.dummy import DummyEngine

ENGINE_ENV_VAR = "KITHORA_ENGINE"
DEFAULT_ENGINE = "dummy"

# Register new engines here: name -> zero-argument constructor.
_ENGINES: dict[str, Callable[[], AsrEngine]] = {
    "dummy": DummyEngine,
}


def available_engines() -> list[str]:
    """Names of all registered engines."""
    return sorted(_ENGINES)


def resolve_engine_name(name: str | None = None) -> str:
    """Normalise ``name`` (or ``$KITHORA_ENGINE``, or the default) and validate it.

    Raises:
        ValueError: if the engine name is not registered.
    """
    raw = name if name is not None else os.environ.get(ENGINE_ENV_VAR, "")
    resolved = raw.strip().lower() or DEFAULT_ENGINE
    if resolved not in _ENGINES:
        raise ValueError(
            f"Unknown ASR engine {resolved!r} (from argument or ${ENGINE_ENV_VAR}); "
            f"available: {', '.join(available_engines())}"
        )
    return resolved


def create_engine(name: str | None = None) -> AsrEngine:
    """Create a fresh engine instance (one per audio stream)."""
    return _ENGINES[resolve_engine_name(name)]()
