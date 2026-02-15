.PHONY: setup run stop clean download load logs build update setup-dev lint test format precompute-phonetic test-frontend test-e2e test-all

setup: build download load precompute-phonetic
	@echo "Setup complete! Run 'make run' to start."

build:
	docker compose build

download:
	./scripts/download-data.sh

load:
	docker compose up -d mongodb
	@echo "Waiting for MongoDB to be healthy..."
	@until docker compose exec mongodb mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; do sleep 1; done
	docker compose run --rm -v "$$(pwd)/data:/data" backend python -m etl.load

update: build
	./scripts/download-data.sh --force
	$(MAKE) load
	$(MAKE) precompute-phonetic
	@echo "Update complete!"

run:
	docker compose up -d
	@echo "App running at http://localhost:8080"
	@echo "API running at http://localhost:8000"

stop:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf data/

setup-dev:  ## Install development dependencies and pre-commit hooks
	@echo "Installing Python development dependencies..."
	pip install -r backend/requirements-dev.txt
	@echo "Installing Node.js development dependencies..."
	npm install
	@echo "Installing pre-commit hooks..."
	pre-commit install
	@echo "Development setup complete!"

lint:  ## Run linters on Python and JavaScript code
	@echo "Running Ruff on Python code..."
	cd backend && ruff check .
	@echo "Running ESLint on JavaScript code..."
	npx eslint frontend/public/js/**/*.js

test:  ## Run Python tests
	@echo "Running pytest..."
	cd backend && pytest

format:  ## Format Python code with Ruff
	@echo "Formatting Python code with Ruff..."
	cd backend && ruff format .

precompute-phonetic:  ## Precompute Dolgopolsky sound classes for concept map
	docker compose up -d mongodb
	@echo "Waiting for MongoDB to be healthy..."
	@until docker compose exec mongodb mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; do sleep 1; done
	@echo "Precomputing phonetic data..."
	docker compose run --rm backend python -m etl.precompute_phonetic

test-frontend:  ## Run Vitest unit tests
	npx vitest run

test-e2e:  ## Run Playwright E2E tests (requires make run)
	npx playwright test

test-all:  ## Run all tests
	$(MAKE) test
	$(MAKE) test-frontend
	$(MAKE) test-e2e
