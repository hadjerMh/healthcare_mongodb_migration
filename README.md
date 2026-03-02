## Migration of the medical dataset to MongoDB

This project contains:

- **a Python script** that migrates the medical dataset (CSV) to **MongoDB**;
- **a Docker / Docker Compose configuration** to run MongoDB and the migration script in a portable way;
- **a description of the data schema**, the authentication system, and user roles;
- **automated integrity checks** before and after migration.

---

### 1. Context

A healthcare client has a large CSV file containing patient hospitalization information. Daily processing on this CSV is becoming hard to evolve and scale.

The goals are to:

- migrate this data to **MongoDB** (a document‑oriented NoSQL database, better suited for horizontal scalability);
- encapsulate the database and scripts in **Docker** containers;
- lay the groundwork for future deployment to the cloud (AWS).

---

### 2. MongoDB database schema

Data is stored in database `healthcare`, collection `patients`.

Example of a final document:

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

**Mapping: CSV columns → MongoDB fields**

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
‑ technical metadata → `_source`

**Indexes created:**

- `idx_medical_condition` : `{ medical_condition: 1 }`
- `idx_doctor_date` : `{ doctor: 1, date_of_admission: -1 }`
‑ `idx_hospital_date`: `{ hospital: 1, date_of_admission: -1 }`

These indexes make the typical queries easier:

- patients by medical condition;
- patients by doctor and date;
- patients by hospital and date.

---

### 3. Authentication system and user roles

If MongoDB authentication is enabled in the container, it can be configured via environment variables such as:

- `MONGO_INITDB_ROOT_USERNAME=admin`
- `MONGO_INITDB_ROOT_PASSWORD=admin_password`
- `MONGO_INITDB_DATABASE=healthcare`

Application users can be created in two complementary ways:

- automatically at container startup via `mongo-init/mongo-init.js`;
- or dynamically by the `main.py` script (function `ensure_app_users`) if the connection user has sufficient privileges.

Target users:

- **`data_ingestor`** (password `ingestor_password`)
  - role: `readWrite` on database `healthcare`
  - usage: running the migration script and ingestion jobs.
- **`data_analyst`** (password `analyst_password`)
  - role: `read` on database `healthcare`
  - usage: read‑only access (dashboards, data analysts, etc.).
- **`admin`** (password `admin`)
  - role: `dbAdmin` on database `healthcare`
  - usage: functional administration of the database (indexes, stats, etc.).

> **Security note**: in a real‑world context, these passwords should:
> - be stored in a secret manager (AWS Secrets Manager, Vault, etc.);
> - be provided at runtime via secure environment variables, not committed in clear text to Git.

---

### 4. Local installation (without Docker)

#### 4.1. Prerequisites

- Python 3.12+
- Dependency manager `uv` (`pip install uv` or official binary)
- MongoDB installed locally (by default on `mongodb://localhost:27017`)

#### 4.2. Create the environment with `uv`

```bash
cd migration_mongodb
uv sync --no-dev
```

#### 4.3. Environment variables (optional)

You can define them in a `.env` file (not committed):

```bash
CSV_PATH=../Data/healthcare_dataset.csv
MONGO_MODE=local
MONGO_DB_NAME=healthcare
MONGO_COLLECTION_NAME=patients
```

#### 4.4. Run the migration locally

With `uv` directly:

```bash
uv run main.py
```

Or via the provided `Makefile` target:

```bash
make run-local
```

---

### 5. Usage with Docker / Docker Compose

#### 5.1. Prerequisites

- Docker
- Docker Compose

#### 5.2. Start MongoDB and the migration

From the `migration_mongodb` folder:

```bash
docker compose up --build
```

This will:

- start a `mongo-healthcare` container with MongoDB and create the database/users (depending on your auth config);
- build a `migration-healthcare` container that:
  - mounts the CSV dataset (`../Data/healthcare_dataset.csv`) under `/data`;
  - runs `uv run main.py`;
  - inserts data into `healthcare.patients`;
  - creates application users if needed;
  - logs the migration.

#### 5.3. Access MongoDB inside the container

From the host:

```bash
docker exec -it mongo-healthcare mongosh -u admin -p admin_password --authenticationDatabase admin healthcare
```

Example commands:

```javascript
db.patients.countDocuments();
db.patients.findOne();
db.patients.find({ medical_condition: "Diabetes" }).limit(5);
```

---

### 6. Automated integrity checks

The `main.py` script performs:

- **Before migration:**
  - row count;
  - detection of missing values per column;
  - count of duplicate rows;
  - inspection of pandas dtypes.
- **During migration:**
  - typed transformation of columns (int, float, date, string);
  - batch insertion (`batch_size`) for better performance.
- **After migration:**
  - counting the number of documents inserted into MongoDB;
  - comparison with the number of CSV rows;
  - index creation.

Results are visible in the logs (console or Docker container logs).

---

### 7. Basic CRUD commands (examples)

Once the migration is done, here are some example MongoDB (`mongosh`) commands:

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

### 8. AWS deployment options (summary)

Several options exist for deploying MongoDB and the related processing on AWS:

- **Amazon EC2 + Docker / self‑managed MongoDB**
  - You deploy MongoDB yourself on EC2 instances.
- **Amazon ECS / Fargate**
  - Container orchestration (MongoDB + Python ingestion service) using the current `Dockerfile` and `docker-compose.yml` (adapted into ECS tasks).
- **Amazon S3**
  - Storage for source files (CSV, exports, backups) in a durable and cost‑effective way.
- **Amazon DocumentDB (MongoDB compatibility)**
  - Managed service compatible with the MongoDB API, an alternative to self‑managed MongoDB to benefit from high availability and automatic backups.

Une présentation PowerPoint (non incluse ici) détaillera le contexte, la démarche technique et la justification de ces choix.

