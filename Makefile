.PHONY: setup run stop clean download load logs build update

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
