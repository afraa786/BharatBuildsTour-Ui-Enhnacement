.PHONY: install hooks lint format test up down logs migrate db-shell

install:
	python3 -m venv server/.venv
	server/.venv/bin/python -m pip install -e 'server[dev]'

hooks:
	server/.venv/bin/pre-commit install

lint:
	server/.venv/bin/ruff check server
	server/.venv/bin/ruff format --check server

format:
	server/.venv/bin/ruff format server
	server/.venv/bin/ruff check --fix server

test:
	server/.venv/bin/pytest server/tests

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f server

migrate:
	docker compose run --rm migrate

db-shell:
	docker compose exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'
