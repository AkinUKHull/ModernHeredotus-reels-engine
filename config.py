"""Shared paths, settings and small helpers used by every script."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "inputs" / "documents"
IMAGES_DIR = BASE_DIR / "inputs" / "images"
OUTPUT_DIR = BASE_DIR / "output"
FONTS_DIR = BASE_DIR / "fonts"

MIN_PYTHON = (3, 10)


class ReelsError(Exception):
    """An expected problem (missing file, bad API key...) with a message meant for the user."""


def setup_console() -> None:
    """Make sure Turkish characters print correctly, even in a Windows console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        found = ".".join(map(str, sys.version_info[:3]))
        wanted = ".".join(map(str, MIN_PYTHON))
        raise ReelsError(
            f"Python {wanted} or newer is required, but this is Python {found}. "
            "See the README, section 'Install Python'."
        )


def load_env() -> None:
    """Read the .env file next to this script. Values in .env win over system variables."""
    try:
        from dotenv import load_dotenv
    except ImportError as exc:
        raise ReelsError(
            "A required library is missing. Run:  pip install -r requirements.txt"
        ) from exc
    load_dotenv(BASE_DIR / ".env", override=True)


def env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def ensure_folders() -> None:
    for folder in (DOCUMENTS_DIR, IMAGES_DIR, OUTPUT_DIR):
        folder.mkdir(parents=True, exist_ok=True)


def newest_first(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)


def show(path: Path) -> str:
    """Print a path relative to the project folder when possible (shorter, friendlier)."""
    try:
        return str(path.resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(path)
