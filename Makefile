.PHONY: bootstrap build down logs migrate openapi test lint typecheck check

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
	docker run --rm -v "$(CURDIR):/output" farebeacon:test python -m farebeacon.scripts.export_openapi /output/openapi.json

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

check: lint typecheck test
