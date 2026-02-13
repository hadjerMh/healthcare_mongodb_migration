## Migration du dataset médical vers MongoDB

Ce projet contient :

- **un script Python** qui migre le dataset de données médicales (CSV) vers **MongoDB** ;
- **une configuration Docker / Docker Compose** pour exécuter MongoDB et le script de migration de manière portable ;
- **une description du schéma de données**, du système d’authentification et des rôles utilisateurs ;
- **des contrôles d’intégrité automatisés** avant et après migration.

---

### 1. Contexte

Un client du domaine médical dispose d’un important fichier CSV contenant les informations d’hospitalisation de ses patients. Les traitements quotidiens sur ce CSV deviennent difficiles à faire évoluer et à scaler.

L’objectif est de :

- migrer ces données vers **MongoDB** (base NoSQL orientée documents, plus adaptée à la scalabilité horizontale) ;
- encapsuler la base et les scripts dans des conteneurs **Docker** ;
- préparer le terrain pour un déploiement futur sur le cloud (AWS).

---

### 2. Schéma de la base de données MongoDB

Les données sont stockées dans la base `healthcare`, dans la collection `patients`.

Exemple de document final :

```json
{
  "_id": ObjectId("..."),
  "name": "Bobby Jackson",
  "age": 30,
  "gender": "Male",
  "blood_type": "B-",
  "medical_condition": "Cancer",
  "date_of_admission": ISODate("2024-01-31T00:00:00Z"),
  "doctor": "Matthew Smith",
  "hospital": "Sons and Miller",
  "insurance_provider": "Blue Cross",
  "billing_amount": 18856.28,
  "room_number": 328,
  "admission_type": "Urgent",
  "discharge_date": ISODate("2024-02-02T00:00:00Z"),
  "medication": "Paracetamol",
  "test_results": "Normal",
  "_source": "csv_healthcare_dataset"
}
```

**Correspondance colonnes CSV → champs MongoDB :**

- `Name` → `name` (string normalisée)
- `Age` → `age` (int)
- `Gender` → `gender` (string)
- `Blood Type` → `blood_type` (string)
- `Medical Condition` → `medical_condition` (string)
- `Date of Admission` → `date_of_admission` (ISODate)
- `Doctor` → `doctor` (string)
- `Hospital` → `hospital` (string)
- `Insurance Provider` → `insurance_provider` (string)
- `Billing Amount` → `billing_amount` (float)
- `Room Number` → `room_number` (int)
- `Admission Type` → `admission_type` (string)
- `Discharge Date` → `discharge_date` (ISODate)
- `Medication` → `medication` (string)
- `Test Results` → `test_results` (string)
- métadonnées techniques → `_source`

**Index créés :**

- `idx_medical_condition` : `{ medical_condition: 1 }`
- `idx_doctor_date` : `{ doctor: 1, date_of_admission: -1 }`
- `idx_hospital_date` : `{ hospital: 1, date_of_admission: -1 }`

Ces index facilitent les requêtes typiques :

- patients par pathologie ;
- patients par médecin et date ;
- patients par hôpital et date.

---

### 3. Système d’authentification et rôles utilisateurs

L’authentification MongoDB est activée dans le conteneur via les variables d’environnement :

- `MONGO_INITDB_ROOT_USERNAME=admin`
- `MONGO_INITDB_ROOT_PASSWORD=admin_password`
- `MONGO_INITDB_DATABASE=healthcare`

Les utilisateurs applicatifs peuvent être créés de deux façons complémentaires :

- automatiquement au démarrage du conteneur via `mongo-init/mongo-init.js` ;
- ou dynamiquement par le script `main.py` (fonction `ensure_app_users`) si l’utilisateur de connexion a les droits suffisants.

Les utilisateurs cibles sont :

- **`data_ingestor`** (mot de passe `ingestor_password`)
  - rôle : `readWrite` sur la base `healthcare`
  - usage : exécution du script de migration et des traitements d’ingestion.
- **`data_analyst`** (mot de passe `analyst_password`)
  - rôle : `read` sur la base `healthcare`
  - usage : accès en lecture seule (tableaux de bord, data analyst, etc.).
- **`admin`** (mot de passe `admin`)
  - rôle : `dbAdmin` sur la base `healthcare`
  - usage : administration fonctionnelle de la base (index, statistiques, etc.).

> **Remarque sécurité** : dans un contexte réel, ces mots de passe doivent être :
> - stockés dans un gestionnaire de secrets (AWS Secrets Manager, Vault, etc.) ;
> - fournis au runtime via des variables d’environnement sécurisées, et non versionnés en clair dans Git.

---

### 4. Installation locale (sans Docker)

#### 4.1. Prérequis

- Python 3.12+
- Gestionnaire de dépendances `uv` (`pip install uv` ou binaire officiel)
- MongoDB installé en local (par défaut sur `mongodb://localhost:27017`)

#### 4.2. Création de l’environnement avec `uv`

```bash
cd migration_mongodb
uv sync --no-dev
```

#### 4.3. Variables d’environnement (optionnel)

Vous pouvez définir dans un fichier `.env` (non versionné) :

```bash
CSV_PATH=../Data/healthcare_dataset.csv
MONGO_MODE=local
MONGO_DB_NAME=healthcare
MONGO_COLLECTION_NAME=patients
```

#### 4.4. Lancer la migration en local

Avec `uv` directement :

```bash
uv run main.py
```

Ou via la cible `Makefile` prévue :

```bash
make run-local
```

---

### 5. Utilisation avec Docker / Docker Compose

#### 5.1. Prérequis

- Docker
- Docker Compose

#### 5.2. Lancer MongoDB et la migration

Depuis le dossier `migration_mongodb` :

```bash
docker compose up --build
```

Cela va :

- démarrer un conteneur `mongo-healthcare` avec MongoDB et création de la base / des utilisateurs (`admin`, `data_ingestor`, `data_analyst`) ;
- construire un conteneur `migration-healthcare` qui :
  - monte le dataset CSV (`../Data/healthcare_dataset.csv`) sous `/data` ;
  - exécute `uv run main.py` ;
  - insère les données dans `healthcare.patients` ;
  - crée les utilisateurs applicatifs si besoin ;
  - log la migration.

#### 5.3. Accès à MongoDB dans le conteneur

Depuis l’hôte :

```bash
docker exec -it mongo-healthcare mongosh -u admin -p admin_password --authenticationDatabase admin healthcare
```

Exemples de commandes :

```javascript
db.patients.countDocuments();
db.patients.findOne();
db.patients.find({ medical_condition: "Diabetes" }).limit(5);
```

---

### 6. Contrôles d’intégrité automatisés

Le script `main.py` effectue :

- **Avant migration :**
  - comptage des lignes ;
  - détection des valeurs manquantes par colonne ;
  - comptage des lignes dupliquées ;
  - inspection des types pandas.
- **Pendant la migration :**
  - transformation typée des colonnes (int, float, date, chaîne) ;
  - insertion par lot (`batch_size`) pour de meilleures performances.
- **Après migration :**
  - comptage du nombre de documents insérés dans MongoDB ;
  - comparaison avec le nombre de lignes du CSV ;
  - création des index.

Les résultats sont visibles dans les logs (console ou logs du conteneur Docker).

---

### 7. Commandes CRUD de base (exemples)

Une fois la migration effectuée, voici quelques exemples de commandes MongoDB (`mongosh`) :

```javascript
// Create
db.patients.insertOne({
  name: "Test Patient",
  age: 40,
  medical_condition: "Asthma"
});

// Read
db.patients.find({ medical_condition: "Diabetes" }).limit(3);

// Update
db.patients.updateOne(
  { name: "Test Patient" },
  { $set: { medical_condition: "Recovered" } }
);

// Delete
db.patients.deleteOne({ name: "Test Patient" });
```

---

### 8. Pistes de déploiement sur AWS (résumé)

Plusieurs options existent pour déployer MongoDB et les traitements associés sur AWS :

- **Amazon EC2 + Docker / MongoDB auto-géré**
  - Vous déployez vous‑même MongoDB dans des instances EC2.
- **Amazon ECS / Fargate**
  - Orchestration de conteneurs (MongoDB + service d’ingestion Python) à partir du `Dockerfile` et du `docker-compose.yml` actuels (à adapter en tâches ECS).
- **Amazon S3**
  - Stockage des fichiers sources (CSV, exports, backups) de manière durable et peu coûteuse.
- **Amazon DocumentDB (compatibilité MongoDB)**
  - Service managé compatible API MongoDB, alternative à MongoDB auto‑géré pour bénéficier de la haute disponibilité et des sauvegardes automatiques.

Une présentation PowerPoint (non incluse ici) détaillera le contexte, la démarche technique et la justification de ces choix.

