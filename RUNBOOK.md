# Bus Booking Platform — Operations Runbook & Incident Response

This runbook provides actionable procedures for managing, maintaining, diagnosing, and recovering the containerized Bus Booking Service in local, staging, and production environments.

---

## 1. Service Port Map & Architecture Overview

| Service | Container Name | Internal Port | Host Port | Protocol | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Nginx Reverse Proxy** | `bus_booking_nginx` | 80, 443 | 80, 443 | HTTP / HTTPS | Edge routing, TLS termination, Security headers |
| **FastAPI Backend** | `bus_booking_app` | 8000 | 8000 | HTTP | Core business API & concurrency locking |
| **PostgreSQL Database** | `bus_booking_db` | 5432 | Isolated | TCP | ACID relational persistence & row locks |

---

## 2. Standard Operational Procedures (SOP)

### 2.1 Starting the Stack Cleanly
To boot up the entire stack with automatic health check orchestration:
```bash
docker compose up -d --build
```
Verify all containers are `(healthy)`:
```bash
docker compose ps
```

### 2.2 Graceful Shutdown & Teardown
To gracefully stop all services without removing database volumes:
```bash
docker compose down
```
To wipe all state (including database volumes) for a completely clean test environment:
```bash
docker compose down -v
```

---

## 3. Observability, Logging & Failure Diagnosis

### 3.1 Inspecting Structured JSON Logs
All incoming requests, latencies, and errors are logged in standardized JSON format.
To follow live application logs:
```bash
docker compose logs -f app
```
To inspect Nginx edge access and error logs:
```bash
docker compose logs -f nginx
```

### 3.2 Health & Readiness Probes
* **Liveness Probe**: Confirms the web process is alive:
  ```bash
  curl -i http://localhost:8000/health
  # Or via HTTPS:
  curl -k -i https://localhost/health
  ```
  Expected Response: `200 OK` `{"status":"healthy","service":"bus-booking-api"}`

* **Readiness Probe**: Confirms the database is connected and accepting queries:
  ```bash
  curl -i http://localhost:8000/ready
  # Or via HTTPS:
  curl -k -i https://localhost/ready
  ```
  Expected Response: `200 OK` `{"status":"ready","database":"connected"}`

---

## 4. Failure Injection & Recovery Drill (Demo Scenario)

To demonstrate fault tolerance and health detection for reviewers:

### Step 1: Deliberately break the database
```bash
docker compose stop db
```

### Step 2: Observe Readiness probe failure
```bash
curl -i http://localhost:8000/ready
```
Output: `HTTP/1.1 503 Service Unavailable` with error detail `Database connection failure`.

### Step 3: Recover the service
```bash
docker compose start db
```
Wait 3–5 seconds for PostgreSQL healthcheck to transition back to healthy.

### Step 4: Verify automatic self-healing
```bash
curl -i http://localhost:8000/ready
```
Output: `HTTP/1.1 200 OK` `{"status":"ready","database":"connected"}`. The service has completely recovered without needing an application restart!

---

## 5. Backup, Disaster Recovery & Restore Procedures

### 5.1 Creating a Hot Database Snapshot
Run the automated backup script:
* **Linux / macOS**:
  ```bash
  bash scripts/backup.sh
  ```
* **Windows (PowerShell)**:
  ```powershell
  .\scripts\backup.ps1
  ```
Snapshots are stored in `./backups/bus_booking_backup_<TIMESTAMP>.sql`.

### 5.2 Restoring from a Snapshot (Disaster Recovery Drill)
Run the automated restore script:
* **Linux / macOS**:
  ```bash
  bash scripts/restore.sh
  ```
* **Windows (PowerShell)**:
  ```powershell
  .\scripts\restore.ps1
  ```

---

## 6. Release Rollback Procedure

If a faulty deployment occurs (e.g., image `sha-bad123`), follow this deterministic rollback:

1. Identify the last known healthy Git commit SHA or Docker tag:
   ```bash
   git log --oneline -n 5
   ```
2. Set the `IMAGE_TAG` environment variable in `.env` to the previous version:
   ```bash
   echo "IMAGE_TAG=sha-good456" >> .env
   ```
3. Redeploy the previous version with zero downtime:
   ```bash
   docker compose up -d app
   ```
4. Verify health status:
   ```bash
   curl -f http://localhost:8000/health
   ```
5. Confirm no database migrations or state corruptions occurred.

---

## 7. Concurrency Acceptance Verification

To prove acceptance criteria #1 ("Prevent duplicate confirmed seat reservations under concurrent requests"):

Run the automated concurrency benchmark:
```bash
python scripts/test_concurrency.py http://localhost:8000
```
This script spawns 4 parallel worker threads requesting the exact same seat simultaneously.
* **Success Criteria**:
  * Exactly 1 thread receives `HTTP 201 Created` with a unique PNR.
  * Exactly 3 threads receive `HTTP 409 Conflict` ("already booked or unavailable").
  * Total database bookings for that seat = 1.
