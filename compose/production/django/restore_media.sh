#!/usr/bin/env bash

### Restore media files from a backup.
###
### Parameters:
###     <1> filename of an existing backup.
###
### Usage:
###     $ docker compose -f docker-compose.production.yml run --rm django /restore_media.sh <backup_filename>

set -o errexit
set -o pipefail
set -o nounset

# Colores para mensajes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

message_warning() {
    echo -e "${BLUE}⚠ $1${NC}"
}

# Configuración
MEDIA_DIR="/app/martina_bescos_app/media"
BACKUP_DIR="/backups/media"

if [[ -z ${1+x} ]]; then
    message_error "Debe especificar el nombre del archivo de backup."
    echo ""
    echo "Uso: $0 <nombre_archivo_backup>"
    echo ""
    message_info "Backups disponibles:"
    ls -lh "${BACKUP_DIR}" | grep "media_backup" | awk '{print "  " $9 " (" $5 ")"}'
    exit 1
fi

backup_filename="${BACKUP_DIR}/${1}"

if [[ ! -f "${backup_filename}" ]]; then
    message_error "No se encontró el backup especificado: ${backup_filename}"
    echo ""
    message_info "Backups disponibles:"
    ls -lh "${BACKUP_DIR}" | grep "media_backup" | awk '{print "  " $9 " (" $5 ")"}'
    exit 1
fi

message_welcome "Restaurando archivos media desde: ${1}"
message_warning "¡ADVERTENCIA! Esto sobrescribirá todos los archivos media actuales."
echo ""
read -p "¿Está seguro de que desea continuar? (escriba 'SI' para confirmar): " confirmation

if [[ "${confirmation}" != "SI" ]]; then
    message_info "Restauración cancelada."
    exit 0
fi

# Crear backup temporal de los archivos actuales
message_info "Creando backup de seguridad de los archivos actuales..."
temp_backup="/backups/media/temp_before_restore_$(date +'%Y_%m_%dT%H_%M_%S').tar.gz"
tar -czf "${temp_backup}" -C "$(dirname ${MEDIA_DIR})" "$(basename ${MEDIA_DIR})" 2>/dev/null || true

# Eliminar contenido actual (pero mantener el directorio)
message_info "Eliminando archivos media actuales..."
rm -rf "${MEDIA_DIR}"/*

# Extraer el backup
message_info "Extrayendo backup..."
if tar -xzf "${backup_filename}" -C "$(dirname ${MEDIA_DIR})"; then
    message_success "Archivos media restaurados exitosamente desde: ${1}"
    message_info "Se creó un backup temporal de los archivos anteriores en: $(basename ${temp_backup})"
else
    message_error "Error al extraer el backup"
    message_info "Restaurando desde backup temporal..."
    tar -xzf "${temp_backup}" -C "$(dirname ${MEDIA_DIR})"
    message_warning "Se restauraron los archivos anteriores debido al error."
    exit 1
fi

message_success "Proceso de restauración completado."
