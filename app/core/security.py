"""Helpers de seguridad y utilidades para tokens y validaciones."""

from __future__ import annotations


def sanitize_token_prefix(token: str | None, prefix_length: int = 8) -> str:
    if not token:
        return ""
    if len(token) <= prefix_length:
        return token
    return f"{token[:prefix_length]}..."
