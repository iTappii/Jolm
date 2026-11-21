SHELL := /bin/bash
VENV := server/.venv
PY := $(VENV)/bin/python
COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

-include .env
export

.PHONY: up down migrate run worker test lint seed import-osm import-transit osm-pbf ci venv

.env:
	cp .env.example .env

up: .env
	$(COMPOSE) up -d --wait postgres

down:
	$(COMPOSE) down

venv: $(VENV)/.installed
$(VENV)/.installed: server/pyproject.toml
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e "server[dev,osm]"
	touch $@

migrate: venv
	$(PY) db/migrate.py

run: venv
	cd server && ../$(PY) -m uvicorn app.main:app --host $${API_HOST:-127.0.0.1} --port $${API_PORT:-8000} --reload

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
