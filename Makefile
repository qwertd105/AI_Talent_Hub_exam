PY ?= python
.PHONY: install test run demo docker

install:
	$(PY) -m pip install -r requirements.txt

test:
	$(PY) -m pytest -q

run:
	$(PY) -m uvicorn app.main:build_app --factory --reload --port 8000

demo:
	$(PY) scripts/demo.py

docker:
	docker compose up --build
