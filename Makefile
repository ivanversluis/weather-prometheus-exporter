IMAGE_NAME ?= weather-prometheus-exporter
PYTHON ?= python3
VENV ?= .venv

.PHONY: install install-dev test coverage compile run docker-build docker-run clean
$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)
$(VENV)/.installed: requirements.txt | $(VENV)/bin/python
	$(VENV)/bin/pip install -r requirements.txt
	touch $@
$(VENV)/.installed-dev: $(VENV)/.installed
	$(VENV)/bin/pip install pytest pytest-cov
	touch $@
install: $(VENV)/.installed
install-dev: $(VENV)/.installed-dev
test: install-dev
	$(VENV)/bin/pytest -v tests
coverage: install-dev
	$(VENV)/bin/pytest tests --cov=exporter --cov-report=term-missing
compile: $(VENV)/bin/python
	$(VENV)/bin/python -m compileall exporter tests
run: install
	$(VENV)/bin/python -m exporter
docker-build:
	docker build -t $(IMAGE_NAME) .
docker-run:
	docker run --rm -p 9100:9100 $(IMAGE_NAME)
clean:
	rm -rf $(VENV) .pytest_cache .coverage htmlcov
