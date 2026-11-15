#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Production Database Restore Drill Utility
# ============================================================

BACKUP_DIR="./backups"
CONTAINER_NAME="bus_booking_db"
DB_USER="postgres"
DB_NAME="bus_booking"

# Find latest backup file if not passed as argument
if [ $# -ge 1 ]; then
    RESTORE_FILE="$1"
else
    RESTORE_FILE=$(ls -t ${BACKUP_DIR}/bus_booking_backup_*.sql 2>/dev/null | head -n 1 || true)
fi

if [ -z "${RESTORE_FILE}" ] || [ ! -f "${RESTORE_FILE}" ]; then
    echo "[ERROR] No valid backup SQL file found in '${BACKUP_DIR}'!" >&2
    echo "Usage: $0 [path_to_backup.sql]"
    exit 1
fi

echo "[INFO] Restoring database from snapshot: ${RESTORE_FILE}..."

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "[ERROR] Database container '${CONTAINER_NAME}' is not running!" >&2
    exit 1
fi

# Execute restore via psql
docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}" < "${RESTORE_FILE}"

echo "[SUCCESS] Database restoration complete from ${RESTORE_FILE}."
