"""HTTP client and strict Open-Meteo payload parsing. Never log URLs."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT = {
    "temperature_2m": "weather_temperature_celsius",
    "apparent_temperature": "weather_apparent_temperature_celsius",
    "relative_humidity_2m": "weather_relative_humidity_percent",
    "pressure_msl": "weather_pressure_hpa",
    "wind_gusts_10m": "weather_wind_gust_kmh",
    "precipitation": "weather_precipitation_mm",
    "shortwave_radiation": "weather_solar_radiation_watts_per_square_meter",
}
HOURLY = {
    "temperature_2m": "weather_forecast_temperature_celsius",
    "precipitation": "weather_forecast_precipitation_mm",
    "shortwave_radiation": "weather_forecast_solar_radiation_watts_per_square_meter",
    "cloud_cover": "weather_forecast_cloud_cover_percent",
}
# Bounded set of forecast lead-hour labels: 48 hours x four metrics.
FORECAST_HOURS = 48


def timestamp(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        # Request uses timezone=UTC; API returns UTC ISO strings without suffix.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def numeric(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("weather value must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("weather value must be finite")
    return result


def parse_payload(payload: dict) -> tuple[dict[str, float], dict[str, list[float]], float, list[float]]:
    if not isinstance(payload, dict):
        raise ValueError("weather payload is not an object")
    current = payload["current"]
    hourly = payload["hourly"]
    times = hourly["time"]
    if not isinstance(current, dict) or not isinstance(hourly, dict) or not isinstance(times, list):
        raise ValueError("invalid weather payload structure")
    now = timestamp(current["time"])
    observations = {name: numeric(current[key]) for key, name in CURRENT.items()}
    # Forecast starts on the current UTC hour. Expose exactly 48 slots with
    # stable, non-identifying horizon_hours labels and forecast valid timestamps.
    start = next((i for i, t in enumerate(times) if timestamp(t) >= now - 3600), None)
    if start is None or len(times) < start + FORECAST_HOURS:
        raise ValueError("fewer than 48 forecast hours")
    valid_times = [timestamp(t) for t in times[start:start + FORECAST_HOURS]]
    series: dict[str, list[float]] = {}
    for field, metric in HOURLY.items():
        values = hourly[field]
        if not isinstance(values, list) or len(values) < start + FORECAST_HOURS:
            raise ValueError("incomplete weather forecast")
        series[metric] = [numeric(x) for x in values[start:start + FORECAST_HOURS]]
    return observations, series, now, valid_times


def fetch_weather(latitude: float, longitude: float, timeout: int = 15):
    # URL contains potentially private coordinates; never include it in errors,
    # logs, traces, or metrics labels. No configurable host / URL is accepted.
    params = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(CURRENT),
        "hourly": ",".join(HOURLY),
        "forecast_hours": 49,
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    })
    request = Request(API_URL + "?" + params, headers={"User-Agent": "weather-prometheus-exporter/0.1"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError("weather API returned a non-200 status")
        payload = json.loads(response.read(262144))
    return parse_payload(payload)
