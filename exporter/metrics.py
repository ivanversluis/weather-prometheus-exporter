"""Bounded Prometheus gauges, cached between Open-Meteo API polls."""
from __future__ import annotations

import logging
import time

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Gauge, start_http_server

from .client import CURRENT, FORECAST_HOURS, HOURLY, fetch_weather
from .config import Config

LOG = logging.getLogger(__name__)


class WeatherMetrics:
    def __init__(self, registry: CollectorRegistry | None = None):
        reg = registry if registry is not None else REGISTRY
        self.up = Gauge("weather_up", "Last Open-Meteo poll succeeded", registry=reg)
        self.last_success = Gauge("weather_last_success_timestamp_seconds", "Time of latest successful API fetch", registry=reg)
        self.observed_at = Gauge("weather_observation_timestamp_seconds", "Time of latest current observation", registry=reg)
        self.poll_errors = Counter("weather_poll_errors_total", "Weather API or payload polling failures", registry=reg)
        self.polls = Counter("weather_polls_total", "Total successful weather API polls", registry=reg)
        self.current = {name: Gauge(name, "Current Open-Meteo observation (" + key + ")", registry=reg)
                        for key, name in CURRENT.items()}
        self.forecast = {name: Gauge(name, "Open-Meteo hourly forecast (" + key + ")",
                                      ["horizon_hours"], registry=reg)
                         for key, name in HOURLY.items()}
        self.forecast_time = Gauge("weather_forecast_valid_timestamp_seconds",
                                   "Forecast validity time per hourly horizon", ["horizon_hours"], registry=reg)
        self.up.set(0)

    def update(self, observations, forecast, observed_at, valid_times, now=None):
        # Validate and stage the entire response in client.parse_payload first.
        for name, value in observations.items():
            self.current[name].set(value)
        for name, values in forecast.items():
            for hour in range(FORECAST_HOURS):
                self.forecast[name].labels(horizon_hours=str(hour)).set(values[hour])
        for hour, value in enumerate(valid_times):
            self.forecast_time.labels(horizon_hours=str(hour)).set(value)
        self.observed_at.set(observed_at)
        self.last_success.set(now if now is not None else time.time())
        self.polls.inc()
        self.up.set(1)

    def fail(self):
        self.poll_errors.inc()
        self.up.set(0)


def poll_once(config: Config, metrics: WeatherMetrics):
    try:
        observations, forecast, observed_at, valid_times = fetch_weather(config.latitude, config.longitude)
        metrics.update(observations, forecast, observed_at, valid_times)
    except Exception:
        # Exception strings may contain the full request URL (private coordinates).
        # Log only the error class, never str(exc), tracebacks or response bodies.
        metrics.fail()
        LOG.warning("Weather poll failed; cached values retained")


def main():
    config = Config.from_env()
    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(message)s")
    start_http_server(config.metrics_port, addr="0.0.0.0")
    LOG.info("Weather metrics server started")
    metrics = WeatherMetricsSingleton.value
    while True:
        poll_once(config, metrics)
        time.sleep(config.poll_interval)


# Instantiate gauges once, before the server's first scrape.
class WeatherMetricsSingleton:
    value = WeatherMetrics()


if __name__ == "__main__":
    main()
