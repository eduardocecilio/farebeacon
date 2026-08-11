.PHONY: bootstrap build down logs migrate openapi test lint typecheck lock check

PYTHON_BUILD_IMAGE := python:3.12.13-alpine3.23@sha256:601d3d3797e90e2534782e69c85fafb7971b43f24c7b1b079b7e48dd435e458d

bootstrap:
	@test -f .env || (cp .env.example .env && echo "Created .env; replace change-me values before starting.")

build:
	docker compose build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose run --rm migrate

openapi:
	docker build -f docker/api.Dockerfile --target test -t farebeacon:test .
	docker run --rm -e FAREBEACON_API_TOKEN=test-openapi-token-with-at-least-thirty-two-characters \
		-v "$(CURDIR):/output" farebeacon:test python -m farebeacon.scripts.export_openapi /output/openapi.json

test:
	docker build -f docker/api.Dockerfile --target test -t farebeacon:test .
	docker run --rm farebeacon:test pytest

lint:
	docker build -f docker/api.Dockerfile --target test -t farebeacon:test .
	docker run --rm farebeacon:test ruff check .
	docker run --rm farebeacon:test ruff format --check .

typecheck:
	docker build -f docker/api.Dockerfile --target test -t farebeacon:test .
	docker run --rm farebeacon:test mypy src

lock:
	docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp/lock-home --tmpfs /tmp:size=512m \
		-v "$(CURDIR):/work" -w /work $(PYTHON_BUILD_IMAGE) sh -lc \
		'python -m pip install --user --quiet "pip-tools==7.6.0" && \
		python -m piptools compile --allow-unsafe --generate-hashes --resolver=backtracking --output-file=requirements-build.lock requirements-build.in && \
		python -m piptools compile --generate-hashes --strip-extras --resolver=backtracking --output-file=requirements.lock pyproject.toml && \
		python -m piptools compile --generate-hashes --strip-extras --resolver=backtracking --extra=dev --output-file=requirements-dev.lock pyproject.toml'

check: lint typecheck test
