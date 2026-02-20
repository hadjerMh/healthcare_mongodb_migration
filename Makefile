launch-docker:
	docker compose up -d

stop-docker:
	docker compose down

clean-docker:
	docker compose down
	docker system prune -a

logs-docker:
	docker compose logs -f

# Exécute la migration contre une instance MongoDB installée en local
run-local:
	CSV_PATH=../Data/healthcare_dataset.csv \
	MONGO_MODE=local \
	MONGO_DB_NAME=healthcare \
	MONGO_COLLECTION_NAME=patients \
	uv run main.py

# Exécute uniquement la migration en se connectant à MongoDB exposé par Docker
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


run-users-init-local:
	mongo mongodb://localhost:27017/admin --username root --password root_password ../migration_mongodb/mongo-init/mongo-init.js

