.PHONY: install dev test lint format migrate revision docker-up docker-down clean

install:
	pip install -e ".[dev]"

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest --cov=src/app --cov-report=term-missing

lint:
	ruff check src tests
	mypy src

format:
	ruff format src tests
	ruff check --fix src tests

migrate:
	alembic upgrade head

revision:
	@test -n "$(m)" || (echo "usage: make revision m=\"description\"" && exit 1)
	alembic revision --autogenerate -m "$(m)"

docker-up:
	docker-compose up -d postgres

docker-down:
	docker-compose down

docker-build:
	docker build -t se-challenge:local .

docker-run:
	docker run --rm -p 8080:8080 --env-file .env se-challenge:local

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf .coverage htmlcov dist build *.egg-info
