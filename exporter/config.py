"""Environment-driven configuration; do not log config values."""
from __future__ import annotations

import math
import os
from dataclasses import dataclass


def _float(name: str, default: str, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name, default)
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside the allowed range")
    return value


def _int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} is outside the allowed range")
    return value


@dataclass(frozen=True)
class Config:
    latitude: float
    longitude: float
    poll_interval: int
    metrics_port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            latitude=_float("WEATHER_LATITUDE", "52.3676", -90, 90),
            longitude=_float("WEATHER_LONGITUDE", "4.9041", -180, 180),
            poll_interval=_int("WEATHER_POLL_INTERVAL_SECONDS", 600, 60, 86400),
            metrics_port=_int("METRICS_PORT", 9100, 1, 65535),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
