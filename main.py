"""
Migration script from CSV to MongoDB.

- Reads the CSV file.
- Transforms rows into Python documents.
- Inserts all documents into a MongoDB collection.

It can run:
- against a locally installed MongoDB (mongod on localhost:27017); or
- against MongoDB running in Docker (port 27017 exposed).

Configuration via environment variables:
- CSV_PATH: path to the CSV file (default ../Data/healthcare_dataset.csv)
- MONGO_URI: MongoDB URI (if not set, a default value is chosen based on MONGO_MODE)
- MONGO_DB_NAME: database name (default healthcare)
- MONGO_COLLECTION_NAME: collection name (default patients)
- MONGO_MODE: "local" (default) or "docker" to adapt the default MONGO_URI.

This script also includes the user/role creation logic
equivalent to the mongo-init/mongo-init.js file:
- data_ingestor: readWrite role on the healthcare database;
- data_analyst: read role on the healthcare database;
- admin: dbAdmin role on the healthcare database.
User creation only succeeds if the MongoDB connection user
has sufficient privileges; otherwise the errors are simply printed.
"""

import os
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient


def get_config():
    load_dotenv()

    csv_path = os.getenv("CSV_PATH", "../Data/healthcare_dataset.csv")

    mode = os.getenv("MONGO_MODE", "local").lower()

    # Default value for MONGO_URI depending on the mode,
    # unless the user explicitly provides MONGO_URI.
    if "MONGO_URI" in os.environ:
        mongo_uri = os.environ["MONGO_URI"]
    elif mode == "docker":
        # MongoDB running in Docker exposed on localhost:27017 without authentication.
        mongo_uri = "mongodb://localhost:27017"
    else:
        # Local mode: mongod installed on the host without authentication.
        mongo_uri = "mongodb://localhost:27017"

    db_name = os.getenv("MONGO_DB_NAME", "healthcare")
    collection_name = os.getenv("MONGO_COLLECTION_NAME", "patients")
    return csv_path, mongo_uri, db_name, collection_name


def ensure_app_users(client, db_name: str) -> None:
    """
    Recreates the logic of mongo-init/mongo-init.js directly in Python.

    Creates 3 users in the target database:
    - data_ingestor: readWrite
    - data_analyst: read
    - admin: dbAdmin

    If the users already exist or if privileges are insufficient,
    the error message is simply printed and the script continues.
    """
    db = client[db_name]

    users_to_create = [
        {
            "user": "data_ingestor",
            "pwd": "ingestor_password",
            "roles": [{"role": "readWrite", "db": db_name}],
        },
        {
            "user": "data_analyst",
            "pwd": "analyst_password",
            "roles": [{"role": "read", "db": db_name}],
        },
        {
            "user": "admin",
            "pwd": "admin",
            "roles": [{"role": "dbAdmin", "db": db_name}],
        },
    ]

    for u in users_to_create:
        try:
            db.command(
                "createUser",
                u["user"],
                pwd=u["pwd"],
                roles=u["roles"],
            )
            print(f"Utilisateur MongoDB créé : {u['user']}")
        except Exception as exc:  # noqa: BLE001
            # Most common case: user already exists or insufficient privileges
            print(f"Unable to create MongoDB user {u['user']} ({exc}). Continuing script.")


def _as_str(value) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _as_int(value) -> int:
    if pd.isna(value):
        return 0
    return int(value)


def _as_float(value) -> float:
    if pd.isna(value):
        return 0.0
    return float(value)


def _as_date(value) -> datetime:
    """
    Parse date values coming from CSV/pandas into a Python datetime.
    Accepts 'YYYY-MM-DD' strings or pandas/py datetime-like values.
    """
    if pd.isna(value):
        # Keep a stable type; downstream code can treat this as "missing".
        return datetime(1970, 1, 1)
    if isinstance(value, datetime):
        return value
    # pandas Timestamp supports to_pydatetime()
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return datetime.strptime(str(value), "%Y-%m-%d")


def row_to_document(row):
    """Convert a CSV row into a MongoDB document with minimal validation."""

    return {
        "patient": {
            "name": _as_str(row["Name"]).strip(),
            "age": _as_int(row["Age"]),
            "gender": _as_str(row["Gender"]),
            "blood_type": _as_str(row["Blood Type"]),
            "medical_condition": _as_str(row["Medical Condition"]),
            "medication": _as_str(row["Medication"]),
            "test_results": _as_str(row["Test Results"]),
        },
        "hospital": {
            "date_of_admission": _as_date(row["Date of Admission"]),
            "doctor": _as_str(row["Doctor"]),
            "hospital": _as_str(row["Hospital"]),
            "insurance_provider": _as_str(row["Insurance Provider"]),
            "billing_amount": _as_float(row["Billing Amount"]),
            "room_number": _as_int(row["Room Number"]),
            "admission_type": _as_str(row["Admission Type"]),
            "discharge_date": _as_date(row["Discharge Date"]),
        },
    }


def migrate():
    csv_path, mongo_uri, db_name, collection_name = get_config()

    print(f"Reading CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"Connecting to MongoDB: {mongo_uri}")
    client = MongoClient(mongo_uri)

    # Create users/roles (equivalent to mongo-init.js) if possible.
    ensure_app_users(client, db_name)

    collection = client[db_name][collection_name]

    print(f"Converting {len(df)} rows to documents…")
    documents = [row_to_document(row) for _, row in df.iterrows()]

    print(f"Inserting {len(documents)} documents into {db_name}.{collection_name}…")
    if documents:
        collection.insert_many(documents)

    print("Migration finished.")
    client.close()


def main():
    migrate()


if __name__ == "__main__":
    main()