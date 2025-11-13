#!/usr/bin/env bash

### Scheduled backup script for cron.
###
### This script is designed to be called from cron and will create
### backups of both the database and media files.

set -o errexit
set -o pipefail
set -o nounset

# Configuración - CAMBIAR ESTAS RUTAS SEGÚN TU INSTALACIÓN
COMPOSE_FILE="$HOME/app-martina-production/docker-compose.production.yml"
COMPOSE_PROJECT_DIR="$HOME/app-martina-production"
LOG_FILE="$HOME/app-martina-production/backups/backup.log"

# Función de log
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "========================================="
log "Iniciando backup automático"
log "========================================="

# Cambiar al directorio del proyecto
cd "${COMPOSE_PROJECT_DIR}"

# 1. Backup de base de datos
log "Creando backup de PostgreSQL..."
if docker compose -f "${COMPOSE_FILE}" exec -T postgres backup >> "${LOG_FILE}" 2>&1; then
    log "✓ Backup de base de datos completado"
else
    log "✗ Error en backup de base de datos"
    exit 1
fi

# 2. Backup de archivos media
log "Creando backup de archivos media..."
if docker compose -f "${COMPOSE_FILE}" run --rm django /backup_media.sh >> "${LOG_FILE}" 2>&1; then
    log "✓ Backup de media completado"
else
    log "✗ Error en backup de media"
    exit 1
fi

log "========================================="
log "Backup automático finalizado exitosamente"
log "========================================="
