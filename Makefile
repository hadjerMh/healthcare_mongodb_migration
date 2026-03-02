launch-docker:
	docker compose up -d

stop-docker:
	docker compose down

clean-docker:
	docker compose down
	docker system prune -a

logs-docker:
	docker compose logs -f

# Run the migration against a MongoDB instance installed locally
run-local:
	CSV_PATH=../Data/healthcare_dataset.csv \
	MONGO_MODE=local \
	MONGO_DB_NAME=healthcare \
	MONGO_COLLECTION_NAME=patients \
	uv run main.py

# Run only the migration by connecting to MongoDB exposed by Docker
run-docker-migration:
	CSV_PATH=../Data/healthcare_dataset.csv \
	MONGO_MODE=docker \
	MONGO_DB_NAME=healthcare \
	MONGO_COLLECTION_NAME=patients \
	uv run main.py

test:
	CSV_PATH=../Data/healthcare_dataset.csv \
	MONGO_MODE=local \
	MONGO_DB_NAME=healthcare_test \
	MONGO_COLLECTION_NAME=patients_test \
	uv run pytest

# Run tests inside the \"migration\" Docker container connected to the Docker MongoDB instance.
test-docker:
	docker compose up -d mongo
	docker compose run --rm \
		-e CSV_PATH=/data/healthcare_dataset.csv \
		-e MONGO_MODE=local \
		-e MONGO_URI=mongodb://mongo:27017 \
		-e MONGO_DB_NAME=healthcare_test \
		-e MONGO_COLLECTION_NAME=patients_test \
		migration uv run pytest


run-users-init-local:
	mongo mongodb://localhost:27017/admin --username root --password root_password ../migration_mongodb/mongo-init/mongo-init.js


# Remove Docker images built for this project
clean-docker-images:
	docker compose down --rmi local
	docker image prune -f
