FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup --system --gid 1000 exporter \
    && adduser --system --uid 1000 --ingroup exporter --no-create-home exporter

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY exporter/ ./exporter/
USER 1000:1000
EXPOSE 9100
CMD ["python", "-m", "exporter"]
