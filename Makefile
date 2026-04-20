SHELL := /bin/bash
-include .env
export

ATLAS := atlas
ATLAS_ENV := local
COMPOSE := docker compose -f docker/docker-compose.local.yml
RUN := $(COMPOSE) run --rm --remove-orphans
EXEC := $(COMPOSE) exec
APP_DB_URL := postgresql://$(APP_DB_USERNAME):$(APP_DB_PASSWORD)@$(APP_DB_HOST):$(APP_DB_PORT)/$(APP_DB_NAME)?sslmode=$(APP_DB_SSLMODE)
APP_ATLAS_DEV_DB_URL := postgresql://$(APP_ATLAS_DEV_DB_USERNAME):$(APP_ATLAS_DEV_DB_PASSWORD)@$(APP_ATLAS_DEV_DB_HOST):$(APP_ATLAS_DEV_DB_PORT)/$(APP_ATLAS_DEV_DB_NAME)?sslmode=$(APP_ATLAS_DEV_DB_SSLMODE)

build:
	$(COMPOSE) build

build-no-cache:
	$(COMPOSE) build --no-cache

build-api:
	$(COMPOSE) build api

up:
	$(COMPOSE) up

down:
	$(COMPOSE) down

update-req:
	uv export --format requirements-txt > requirements.txt
	uv export --format requirements-txt --group dev > requirements-dev.txt

all-check: format test typecheck lint-fix

typecheck:
	$(RUN) api mypy ./src

format:
	$(RUN) api python -m ruff format ./src

format-check:
	$(RUN) api python -m ruff format ./src --check

lint:
	$(RUN) api python -m ruff check ./src

lint-fix:
	$(RUN) api python -m ruff check ./src --fix

test:
	$(RUN) api python -m pytest

draw-graph:
	$(RUN) api python scripts/draw_graph.py

publish:
	ngrok http --domain=$(LOCAL_PUBLISH_DOMAIN) 8000

atlas-version:
	$(RUN) atlas version

atlas-inspect:
	$(RUN) atlas schema inspect --env local

atlas-apply:
	$(RUN) atlas schema apply --env local --config "file://app/atlas.hcl"

atlas-apply-test:
	$(RUN) atlas schema apply --env test --config "file://app/atlas.hcl"

rm-volumes:
	docker compose -f docker/docker-compose.local.yml down --volumes

ps:
	$(COMPOSE) ps

shell-%:
	$(EXEC) $* bash || $(EXEC) $* sh || $(EXEC) $* ash

shell-run-%:
	$(RUN) --entrypoint bash $* || $(RUN) --entrypoint sh $* || $(RUN) --entrypoint ash $*

db:
	$(EXEC) db psql "$(APP_DB_URL)"

db-atlas-dev:
	$(EXEC) db_dev psql "$(APP_ATLAS_DEV_DB_URL)"
