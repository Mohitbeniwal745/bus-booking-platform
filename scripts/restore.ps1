# ============================================================
# Production Database Restore Drill Utility (PowerShell)
# ============================================================
param (
    [string]$RestoreFile = ""
)
$ErrorActionPreference = "Stop"

$BackupDir = ".\backups"
$ContainerName = "bus_booking_db"
$DbUser = "postgres"
$DbName = "bus_booking"

if (-not $RestoreFile) {
    $latest = Get-ChildItem -Path "$BackupDir\bus_booking_backup_*.sql" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        $RestoreFile = $latest.FullName
    }
}

if (-not $RestoreFile -or -not (Test-Path -Path $RestoreFile)) {
    Write-Error "[ERROR] No valid backup SQL file found to restore!"
    exit 1
}

Write-Host "[INFO] Restoring database from snapshot: $RestoreFile..." -ForegroundColor Cyan

$running = docker ps --format '{{.Names}}' | Select-String "^$ContainerName$"
if (-not $running) {
    Write-Error "[ERROR] Database container '$ContainerName' is not running!"
    exit 1
}

# Pipe SQL into docker container psql
Get-Content -Raw $RestoreFile | docker exec -i $ContainerName psql -U $DbUser -d $DbName

Write-Host "[SUCCESS] Database restoration complete from $RestoreFile." -ForegroundColor Green
