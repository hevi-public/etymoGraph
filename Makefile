.PHONY: setup run stop clean download load logs build update setup-dev lint test acceptance format precompute-phonetic precompute-edges test-frontend test-e2e test-integration test-all collect-fixtures capture-layout-snapshots bench-layout-baseline bench-layout-server

setup: build download load
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

test:  ## Run Python tests (hermetic: unit + acceptance, no live stack)
	@echo "Running pytest..."
	cd backend && pytest

acceptance:  ## Run the hermetic acceptance tier only (SPC-00020, no live stack)
	@echo "Running acceptance tier (in-process app via httpx ASGITransport)..."
	cd backend && pytest -m acceptance $(FLAGS)

format:  ## Format Python code with Ruff
	@echo "Formatting Python code with Ruff..."
	cd backend && ruff format .

precompute-phonetic:  ## Precompute Dolgopolsky sound classes for concept map
	@echo "Precomputing phonetic data (requires lingpy + pymongo)..."
	cd backend && python -m etl.precompute_phonetic

precompute-edges:  ## Precompute compound/affix etymology edges (pass --reprocess via FLAGS to rebuild)
	@echo "Precomputing compound/affix edges (requires pymongo)..."
	cd backend && python -m etl.precompute_edges $(FLAGS)

test-frontend:  ## Run Vitest unit tests
	npx vitest run

test-e2e:  ## Run Playwright E2E tests (requires make run)
	npx playwright test

test-integration:  ## Run live-API characterization tests (SPC-00013, requires make run)
	pytest tests/integration $(FLAGS)

test-all:  ## Run all tests
	$(MAKE) test
	$(MAKE) test-frontend
	$(MAKE) test-e2e
	$(MAKE) test-integration

collect-fixtures:  ## Regenerate Wiktionary example fixtures (SPC-00013, requires make run)
	python scripts/collect_wiktionary_examples.py --all $(FLAGS)

capture-layout-snapshots:  ## Regenerate layout characterization snapshots (SPC-00021 §9, requires make run)
	python scripts/capture_layout_snapshots.py

bench-layout-baseline:  ## Measure client-physics layout baseline (SPC-00021 §10, requires make run; never in CI)
	LAYOUT_BASELINE=1 npx playwright test tests/e2e/layout-baseline.spec.js --workers=1 $(FLAGS)

bench-layout-server:  ## Measure server-streamed layout settle, cold+warm (SPC-00021 §10; drop the layouts collection first for cold)
	LAYOUT_BASELINE=1 LAYOUT_BASELINE_MODE=server npx playwright test tests/e2e/layout-baseline.spec.js --workers=1 $(FLAGS)
