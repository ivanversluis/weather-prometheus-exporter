# Weather Prometheus Exporter

Privacy-aware [Open-Meteo](https://open-meteo.com/en/docs) current weather and hourly 48-hour forecast exporter, with a Python 3.12 container and GitHub Actions/GHCR pipeline modeled after the DSMR P1 exporter.

## Operation

- Default public location: **Amsterdam city centre** (52.3676, 4.9041); not a private home address.
- Poll Open-Meteo every **600 seconds** (10 minutes); cache results in memory.
- Expose `/metrics` on port 9100 for Prometheus scraping (homelabs config: **900 seconds**, 15 minutes).
- Current observations: temperature, feels-like, relative humidity, pressure, wind gusts, precipitation and solar irradiance.
- Next 48 UTC hours: forecast temperature, precipitation, cloud cover, solar radiation and each timestamp, with bounded `horizon_hours="0".."47"` labels.
- Expose last successful fetch time and `weather_up`; on API errors, retain previously cached values but mark `weather_up=0`. No unexpected zeros in climate or solar panels.
- Log a concise `Open-Meteo GET /v1/forecast HTTP 200` line after each successful refresh (every 10 minutes). HTTP failures log only their numeric status; other failures log a generic message. **Never log request URLs, location coordinates, HTTP error bodies or exception strings.**

**Important for Grafana:** Prometheus default instant-query lookback is 5 minutes. With a 15-minute scrape interval, use `last_over_time(weather_temperature_celsius[30m])` or similar instead of an instant `weather_temperature_celsius` query. Use `time() - last_over_time(weather_last_success_timestamp_seconds[30m])` to detect stale source data. For automation, require fresh values and `weather_up == 1`; forecasts are models, not measurements. Data timestamps are UTC.

## Environment configuration

| Variable | Default | Purpose |
|---|---|---|
| `WEATHER_LATITUDE` | `52.3676` | Public Amsterdam centre by default; use private env/Secret for your own coordinates |
| `WEATHER_LONGITUDE` | `4.9041` | See above |
| `WEATHER_POLL_INTERVAL_SECONDS` | `600` | Open-Meteo request frequency |
| `METRICS_PORT` | `9100` | Local Prometheus endpoint |
| `LOG_LEVEL` | `INFO` | Diagnostics (never prints coordinates or request URLs) |

Do **not** commit personal coordinates, precise home coordinates, or override files. Environment files are gitignored. In Kubernetes, use an optional Secret called `weather-prometheus-exporter-location` containing `WEATHER_LATITUDE` and `WEATHER_LONGITUDE`; Secret values override the public ConfigMap defaults. Keep private overrides out of version control, GitHub issue/PR descriptions, dashboard variables, Prometheus target labels, and logs. An optional Secret added after deployment requires a pod restart to read new environment variables. Coordinates are necessarily sent over HTTPS to the Open-Meteo service.

## Develop

```bash
make install-dev
make test
make compile
make docker-build
docker run --rm -p 9100:9100 ghcr.io/ivanversluis/weather-prometheus-exporter:latest
curl -s localhost:9100/metrics | grep '^weather_'
```

On pull requests, GitHub Actions validates Python and builds the Docker image without pushing. After merge to `main`, it pushes `latest`, `main`, and `sha-*` to GHCR. Version tags `v*` publish their own image tag. Kubernetes deployment uses the release tag `v0.1.0` and must wait for that release to be published; no automatic deployment before the image exists.

## Privacy and safety

- No latitude, longitude, city name, query URL or user identifiers in metrics labels.
- Never log full HTTP exceptions or Open-Meteo request URLs; their query strings contain coordinates.
- Validate all environmental coordinates and every required numeric field; reject malformed or partial forecast responses.
- Only the fixed `https://api.open-meteo.com/v1/forecast` endpoint is contacted.
- One exporter replica; no API tokens required for non-commercial Open-Meteo use.
- Keep heating or EV control as a separate, fail-safe consumer; the exporter is read-only and makes no control decisions.
