# ============================================================
# Production Database Snapshot & Backup Utility (PowerShell)
# ============================================================
$ErrorActionPreference = "Stop"

$BackupDir = ".\backups"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = "$BackupDir\bus_booking_backup_$Timestamp.sql"
$ContainerName = "bus_booking_db"
$DbUser = "postgres"
$DbName = "bus_booking"

if (!(Test-Path -Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

Write-Host "[INFO] Starting database backup for '$DbName'..." -ForegroundColor Cyan

$running = docker ps --format '{{.Names}}' | Select-String "^$ContainerName$"
if (-not $running) {
    Write-Error "[ERROR] Database container '$ContainerName' is not running!"
    exit 1
}

docker exec -t $ContainerName pg_dump -U $DbUser -d $DbName --clean --if-exists > $BackupFile

if ((Test-Path -Path $BackupFile) -and ((Get-Item $BackupFile).Length -gt 0)) {
    $size = (Get-Item $BackupFile).Length
    Write-Host "[SUCCESS] Backup created successfully: $BackupFile ($size bytes)" -ForegroundColor Green
} else {
    Write-Error "[ERROR] Backup failed or generated empty snapshot!"
    exit 1
}
