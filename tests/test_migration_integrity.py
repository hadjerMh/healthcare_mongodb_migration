import os
import sys
from pathlib import Path

import pandas as pd
import pytest
from pymongo import MongoClient

# Ensure "import main" works even when pytest is launched from project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import main as migration_main


TEST_DB_NAME = "healthcare_test"
TEST_PATIENT_COLLECTION_NAME = "patients_test"


def _mongo_client() -> MongoClient:
    """Small helper to create a Mongo client for tests."""
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    return MongoClient(uri)


@pytest.fixture()
def migration_result(monkeypatch):
    """
    Run one migration into a test patients collection.
    Returns (patients_collection, source_dataframe).
    """
    client = _mongo_client()

    # Configure main.py to use a dedicated test DB / collection.
    # CSV_PATH and MONGO_MODE can be overridden from the environment (e.g. in Docker).
    csv_path = os.getenv("CSV_PATH", "../Data/healthcare_dataset.csv")
    mongo_mode = os.getenv("MONGO_MODE", "local")

    monkeypatch.setenv("CSV_PATH", csv_path)
    monkeypatch.setenv("MONGO_MODE", mongo_mode)
    monkeypatch.setenv("MONGO_DB_NAME", TEST_DB_NAME)
    monkeypatch.setenv("MONGO_COLLECTION_NAME", TEST_PATIENT_COLLECTION_NAME)

    patients_collection = client[TEST_DB_NAME][TEST_PATIENT_COLLECTION_NAME]
    patients_collection.drop()

    # Run the real migration
    migration_main.migrate()

    csv_path, _, _, _ = migration_main.get_config()
    df = pd.read_csv(csv_path)

    yield patients_collection, df

    # Cleanup
    client.drop_database(TEST_DB_NAME)
    client.close()


def test_row_count_matches_csv(migration_result):
    """Same number of documents in Mongo as rows in the CSV."""
    patients_collection, df = migration_result
    assert patients_collection.count_documents({}) == len(df)


def test_collection_not_empty(migration_result):
    """At least one document has been inserted."""
    patients_collection, _ = migration_result
    assert patients_collection.count_documents({}) > 0


def test_document_has_expected_fields(migration_result):
    """A sample document contains all expected fields."""
    patients_collection, _ = migration_result
    doc = patients_collection.find_one()
    assert doc is not None

    # Check top-level structure
    assert "patient" in doc
    assert "hospital" in doc

    patient = doc["patient"]
    hospital = doc["hospital"]

    expected_patient_fields = {
        "name",
        "age",
        "gender",
        "blood_type",
        "medical_condition",
        "medication",
        "test_results",
    }

    expected_hospital_fields = {
        "date_of_admission",
        "doctor",
        "hospital",
        "insurance_provider",
        "billing_amount",
        "room_number",
        "admission_type",
        "discharge_date",
    }

    assert expected_patient_fields.issubset(set(patient.keys()))
    assert expected_hospital_fields.issubset(set(hospital.keys()))


def test_first_50_documents_share_same_keys(migration_result):
    """First 50 documents have the same key set (schema consistency)."""
    patients_collection, _ = migration_result
    docs = list(patients_collection.find().limit(50))
    assert docs, "No documents found"

    base_keys = set(docs[0].keys())
    for d in docs[1:]:
        assert set(d.keys()) == base_keys


def test_no_null_name_field(migration_result):
    """No document has a null 'name'."""
    patients_collection, _ = migration_result
    # Check nested field patient.name
    assert patients_collection.count_documents({"patient.name": None}) == 0

