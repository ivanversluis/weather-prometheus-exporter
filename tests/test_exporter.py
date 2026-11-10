import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from prometheus_client import CollectorRegistry

from exporter.client import CURRENT, HOURLY, FORECAST_HOURS, fetch_weather, parse_payload
from exporter.config import Config
from exporter.metrics import WeatherMetrics, poll_once


def payload():
    base = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
    result = {
        "current": {"time": "2026-11-10T12:15"},
        "hourly": {"time": [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M")
                            for i in range(49)]},
    }
    result["current"].update({name: 5.5 for name in CURRENT})
    result["hourly"].update({name: [float(i) for i in range(49)] for name in HOURLY})
    return result


def test_parse_full_48_hour_forecast():
    observations, forecasts, observed_at, valid_times = parse_payload(payload())
    assert len(valid_times) == FORECAST_HOURS
    assert forecasts["weather_forecast_temperature_celsius"][47] == 47
    assert observed_at == 1794312900.0
    assert observations["weather_temperature_celsius"] == 5.5


def test_reject_incomplete_forecast():
    data = payload()
    data["hourly"]["temperature_2m"] = [1]
    with pytest.raises(ValueError, match="incomplete"):
        parse_payload(data)


def test_reject_nonfinite_and_missing_values():
    for bad in [None, float("nan"), True]:
        data = payload()
        data["current"]["temperature_2m"] = bad
        with pytest.raises(ValueError):
            parse_payload(data)


def test_configuration_city_default_and_private_values_not_logged(monkeypatch):
    monkeypatch.delenv("WEATHER_LATITUDE", raising=False)
    monkeypatch.delenv("WEATHER_LONGITUDE", raising=False)
    conf = Config.from_env()
    assert conf.latitude == 52.3676
    assert conf.longitude == 4.9041
    monkeypatch.setenv("WEATHER_LATITUDE", "999.1")
    with pytest.raises(ValueError) as error:
        Config.from_env()
    assert "999.1" not in str(error.value)


def test_http_query_uses_48_hour_data_and_static_host():
    from io import BytesIO
    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return json.dumps(payload()).encode()
    with patch("exporter.client.urlopen", return_value=Response()) as op:
        result = fetch_weather(52.3676, 4.9041)
    url = op.call_args.args[0].full_url
    assert url.startswith("https://api.open-meteo.com/v1/forecast?")
    assert "forecast_hours=49" in url
    assert len(result[3]) == 48


def test_metrics_update_and_failure_keeps_last_values():
    reg = CollectorRegistry()
    metrics = WeatherMetrics(reg)
    obs, forecasts, obs_time, valid_times = parse_payload(payload())
    metrics.update(obs, forecasts, obs_time, valid_times, now=100)
    assert reg.get_sample_value("weather_up") == 1
    assert reg.get_sample_value("weather_temperature_celsius") == 5.5
    assert reg.get_sample_value("weather_forecast_temperature_celsius", {"horizon_hours": "47"}) == 47
    assert reg.get_sample_value("weather_last_success_timestamp_seconds") == 100
    metrics.fail()
    assert reg.get_sample_value("weather_up") == 0
    assert reg.get_sample_value("weather_temperature_celsius") == 5.5


def test_api_failure_does_not_log_coordinates(caplog):
    from exporter.client import API_URL
    reg = CollectorRegistry()
    metrics = WeatherMetrics(reg)
    config = Config(12.345678, 123.456789, 600, 9100, "INFO")
    with patch("exporter.metrics.fetch_weather", side_effect=RuntimeError(
            API_URL + "?latitude=12.345678&longitude=123.456789")):
        poll_once(config, metrics)
    assert "12.345678" not in caplog.text
    assert "123.456789" not in caplog.text
    assert reg.get_sample_value("weather_up") == 0
