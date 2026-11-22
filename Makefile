SHELL := /bin/bash
VENV := server/.venv
PYTHON ?= python3.12
PY := $(VENV)/bin/python
COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

-include .env
export

.PHONY: up down migrate run worker test lint seed import-osm import-transit import-addresses osm-pbf ci venv

.env:
	cp .env.example .env

up: .env
	$(COMPOSE) up -d --wait postgres

down:
	$(COMPOSE) down

venv: $(VENV)/.installed
$(VENV)/.installed: server/pyproject.toml
	@test -x "$(PY)" || "$(PYTHON)" -m venv "$(VENV)"
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e "server[dev,osm]"
	touch $@

migrate: venv
	$(PY) db/migrate.py

run: venv
	cd server && ../$(PY) -m uvicorn app.main:app --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000} --reload --no-proxy-headers

worker: venv
	cd server && ../$(PY) -m app.worker

test: venv
	cd server && ../$(PY) -m pytest -q

lint: venv
	$(VENV)/bin/ruff check server db data
	$(VENV)/bin/ruff format --check server db data

seed: venv
	$(PY) data/seed/load_seed.py

# Almaty places from OpenStreetMap (Ш-08); needs `make migrate seed` first. Install pyosmium: pip install -e "server[osm]"
# One shared OSM extract (places import, transit import, Valhalla): data/osm/cache/kazakhstan.osm.pbf.
# Reuses maps/build/kazakhstan.osm.pbf if present, else downloads from Geofabrik. REFRESH=1 re-downloads.
osm-pbf:
	./data/osm/fetch_pbf.sh

import-osm: venv osm-pbf
	$(VENV)/bin/pip install -q -e "server[osm]"
	$(PY) data/osm/import_places.py

# Public transport (Ш-21): metro/bus/trolleybus stops and routes from OSM + data/seed/transit_manual.csv
import-transit: venv osm-pbf
	$(VENV)/bin/pip install -q -e "server[osm]"
	$(PY) data/osm/import_transit.py

# Addresses and named buildings for reverse geocoding (Ш-23c); idempotent, ~1-2 min
import-addresses: venv osm-pbf
	$(VENV)/bin/pip install -q -e "server[osm]"
	$(PY) data/osm/import_addresses.py

# Map (Ш-11/Ш-12): build vector tiles, regenerate styles, serve maps/ with Range support
.PHONY: tiles tiles-styles tiles-serve
tiles:
	./maps/build_tiles.sh

tiles-styles:
	python3 maps/style/build_styles.py

tiles-serve:
	python3 maps/serve.py 8080

# Admin panel (Ш-10): make admin-create EMAIL=you@example.com  (password is prompted / read from stdin)
.PHONY: admin-create
admin-create: venv
	@test -n "$(EMAIL)" || { echo "usage: make admin-create EMAIL=you@example.com"; exit 2; }
	cd server && ../$(PY) -m app.admin.cli create "$(EMAIL)"

# Routing (Ш-20): Valhalla in Docker. First start builds tiles from data/osm/cache/kazakhstan.osm.pbf
# into the `valhalla_data` volume (several minutes); later starts reuse them.
.PHONY: valhalla-up valhalla-down valhalla-logs valhalla-rebuild
valhalla-up: .env osm-pbf
	$(COMPOSE) --profile valhalla up -d --wait --wait-timeout 1800 valhalla

valhalla-down:
	$(COMPOSE) --profile valhalla stop valhalla
	$(COMPOSE) --profile valhalla rm -f valhalla

valhalla-logs:
	$(COMPOSE) --profile valhalla logs -f valhalla

# Drop built tiles (e.g. after replacing the PBF) and rebuild on next `make valhalla-up`
valhalla-rebuild: valhalla-down
	docker volume rm jol_valhalla_data

ci: lint test

# Production scaffolding (Ш-51). Nothing here picks a host or pushes anything on its own.
# Details and env variables: docs/deploy.md and the header of infra/deploy.sh.
#   make deploy-build | deploy-check | deploy-migrate | deploy-up | deploy-rollback | deploy-status
#   make deploy-push REGISTRY=ghcr.io/org     (explicit; `deploy-up` never pushes)
.PHONY: backup backup-verify secrets-generate
deploy-%:
	infra/deploy.sh $*

backup: venv
	infra/backup.sh

# Restore drill on the local dev database: dump, restore into jol_restore_scratch, compare the row
# counts of every table, then remove the scratch database. Never touches the dev database itself.
backup-verify: venv up
	mkdir -p infra/.backups-verify; \
	export PG_DOCKER_CONTAINER=$$($(COMPOSE) ps -q postgres) PG_USER=$${POSTGRES_USER:-jol} \
	  BACKUP_DB=$${POSTGRES_DB:-jol} BACKUP_DIR=infra/.backups-verify BACKUP_KEEP_LOCAL=1 \
	  DATABASE_URL="$(DATABASE_URL)" VERIFY_SOURCE_URL="$(DATABASE_URL)" DROP_SCRATCH=1 \
	  PATH="$(CURDIR)/$(VENV)/bin:$$PATH"; \
	infra/backup.sh && \
	infra/restore.sh "$$(ls -t infra/.backups-verify/jol-*.dump | head -1)" jol_restore_scratch

# New secrets for a .env.prod (JWT / OTP / Apple nonce / token encryption)
secrets-generate: venv
	cd server && ../$(PY) -m app.auth.keys generate

# Ш-53: one real prompt to DeepSeek (needs DEEPSEEK_API_KEY in .env; without it explains what to do)
.PHONY: llm-smoke
llm-smoke: venv
	cd server && ../$(PY) -m app.providers.llm.smoke

# Ш-55: local S3-compatible storage for place photos (dev only); see docs/photos.md
.PHONY: minio-up minio-down
minio-up: .env
	$(COMPOSE) --profile minio up -d --wait minio
	$(COMPOSE) --profile minio up minio-init

minio-down:
	$(COMPOSE) --profile minio stop minio
