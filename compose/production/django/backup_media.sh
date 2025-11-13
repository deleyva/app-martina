#!/usr/bin/env bash

### Create a backup of media files.
###
### Usage:
###     $ docker compose -f docker-compose.production.yml run --rm django /backup_media.sh

set -o errexit
set -o pipefail
set -o nounset

# Colores para mensajes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

message_welcome() {
    echo -e "${GREEN}$1${NC}"
}

message_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

message_error() {
    echo -e "${RED}✗ $1${NC}"
}

message_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Configuración
MEDIA_DIR="/app/martina_bescos_app/media"
BACKUP_DIR="/backups/media"
BACKUP_PREFIX="media_backup"
DAYS_TO_KEEP=30  # Mantener backups de los últimos 30 días

# Crear directorio de backups si no existe
mkdir -p "${BACKUP_DIR}"

message_welcome "Iniciando backup de archivos media..."

# Verificar que el directorio media existe
if [[ ! -d "${MEDIA_DIR}" ]]; then
    message_error "El directorio de media '${MEDIA_DIR}' no existe."
    exit 1
fi

# Crear nombre de archivo con fecha
backup_filename="${BACKUP_PREFIX}_$(date +'%Y_%m_%dT%H_%M_%S').tar.gz"
backup_path="${BACKUP_DIR}/${backup_filename}"

message_info "Creando backup en: ${backup_path}"

# Crear el backup (tar con compresión gzip)
if tar -czf "${backup_path}" -C "$(dirname ${MEDIA_DIR})" "$(basename ${MEDIA_DIR})" 2>/dev/null; then
    # Obtener tamaño del backup
    backup_size=$(du -h "${backup_path}" | cut -f1)
    message_success "Backup creado exitosamente: ${backup_filename} (${backup_size})"
else
    message_error "Error al crear el backup"
    exit 1
fi

# Limpiar backups antiguos
message_info "Limpiando backups antiguos (más de ${DAYS_TO_KEEP} días)..."
find "${BACKUP_DIR}" -name "${BACKUP_PREFIX}_*.tar.gz" -type f -mtime +${DAYS_TO_KEEP} -delete

# Mostrar lista de backups disponibles
message_info "Backups disponibles:"
ls -lh "${BACKUP_DIR}" | grep "${BACKUP_PREFIX}" | awk '{print "  " $9 " (" $5 ")"}'

# Mostrar espacio en disco
df -h "${BACKUP_DIR}" | tail -n 1 | awk '{print "\nEspacio en disco: " $5 " usado de " $2}'

message_success "Proceso de backup completado."
