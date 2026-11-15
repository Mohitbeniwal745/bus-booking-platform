#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Production Database Snapshot & Backup Utility
# ============================================================

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/bus_booking_backup_${TIMESTAMP}.sql"
CONTAINER_NAME="bus_booking_db"
DB_USER="postgres"
DB_NAME="bus_booking"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Starting database backup for '${DB_NAME}'..."

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[ERROR] Database container '${CONTAINER_NAME}' is not running!" >&2
    exit 1
fi

docker exec -t "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" --clean --if-exists > "${BACKUP_FILE}"

# Verify file was generated and is not empty
if [ -s "${BACKUP_FILE}" ]; then
    FILE_SIZE=$(wc -c < "${BACKUP_FILE}")
    echo "[SUCCESS] Backup created successfully: ${BACKUP_FILE} (${FILE_SIZE} bytes)"
else
    echo "[ERROR] Backup failed or generated empty snapshot!" >&2
    exit 1
fi
