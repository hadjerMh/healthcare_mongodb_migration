"""
Script de migration très simple du CSV vers MongoDB.

- Lit le fichier CSV.
- Transforme les lignes en documents Python.
- Insère tous les documents dans une collection MongoDB.

Il peut fonctionner :
- avec un MongoDB installé localement (mongod sur localhost:27017) ;
- ou avec un MongoDB dans Docker (port 27017 exposé).

Configuration par variables d'environnement :
- CSV_PATH : chemin du fichier CSV (défaut ../Data/healthcare_dataset.csv)
- MONGO_URI : URI de MongoDB (si non défini, une valeur par défaut est choisie selon MONGO_MODE)
- MONGO_DB_NAME : nom de la base (défaut healthcare)
- MONGO_COLLECTION_NAME : nom de la collection (défaut patients)
- MONGO_MODE : "local" (défaut) ou "docker" pour adapter le MONGO_URI par défaut.

Ce script intègre aussi la logique de création d'utilisateurs / rôles
équivalente à celle du fichier mongo-init/mongo-init.js :
- data_ingestor : rôle readWrite sur la base healthcare ;
- data_analyst : rôle read sur la base healthcare ;
- admin : rôle dbAdmin sur la base healthcare.
La création réussira uniquement si l'utilisateur de connexion MongoDB
dispose des droits suffisants; sinon les erreurs sont simplement affichées.
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

    # Valeur par défaut du MONGO_URI selon le mode, sauf si l'utilisateur fournit explicitement MONGO_URI.
    if "MONGO_URI" in os.environ:
        mongo_uri = os.environ["MONGO_URI"]
    elif mode == "docker":
        # Exemple : MongoDB dans Docker exposé sur localhost:27017 avec utilisateur applicatif.
        mongo_uri = "mongodb://app_ingestor:ingestor_password@localhost:27017/healthcare?authSource=admin"
    else:
        # Mode local : mongod installé sur la machine sans authentification particulière.
        mongo_uri = "mongodb://localhost:27017"

    db_name = os.getenv("MONGO_DB_NAME", "healthcare")
    collection_name = os.getenv("MONGO_COLLECTION_NAME", "patients")
    return csv_path, mongo_uri, db_name, collection_name


def ensure_app_users(client, db_name: str) -> None:
    """
    Recrée la logique de mongo-init/mongo-init.js directement en Python.

    Crée 3 utilisateurs dans la base cible :
    - data_ingestor : readWrite
    - data_analyst : read
    - admin : dbAdmin

    Si les utilisateurs existent déjà ou que les droits sont insuffisants,
    on affiche simplement le message et on continue.
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
            # Le cas le plus fréquent : l'utilisateur existe déjà ou pas assez de droits
            print(f"Impossible de créer l'utilisateur {u['user']} ({exc}). Suite du script.")


def row_to_document(row):
    """Convertit une ligne du CSV en document MongoDB sans beaucoup de vérifications."""
    return {
        
        "name": str(row["Name"]),
        "age": int(row["Age"]),
        "gender": str(row["Gender"]),
        "blood_type": row["Blood Type"],
        "medical_condition": str(row["Medical Condition"]),
        "date_of_admission": datetime.strptime(row["Date of Admission"], "%Y-%m-%d"),
        "doctor": row["Doctor"],
        "hospital": str(row["Hospital"]),
        "insurance_provider": row["Insurance Provider"],
        "billing_amount": float(row["Billing Amount"]),
        "room_number": row["Room Number"],
        "admission_type": str(row["Admission Type"]),
        "discharge_date": datetime.strptime(row["Discharge Date"], "%Y-%m-%d"),
        "medication": row["Medication"],
        "test_results": str(row["Test Results"]),
    }


def migrate():
    csv_path, mongo_uri, db_name, collection_name = get_config()

    print(f"Lecture du CSV : {csv_path}")
    df = pd.read_csv(csv_path)

    print(f"Connexion à MongoDB : {mongo_uri}")
    client = MongoClient(mongo_uri)

    # Création des utilisateurs / rôles (équivalent mongo-init.js) si possible.
    ensure_app_users(client, db_name)

    collection = client[db_name][collection_name]

    print(f"Conversion de {len(df)} lignes en documents…")
    documents = [row_to_document(row) for _, row in df.iterrows()]

    print(f"Insertion de {len(documents)} documents dans {db_name}.{collection_name}…")
    if documents:
        collection.insert_many(documents)

    print("Migration terminée.")
    client.close()


def main():
    migrate()


if __name__ == "__main__":
    main()