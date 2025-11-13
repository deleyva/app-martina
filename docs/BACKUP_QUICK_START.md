# 🚀 Guía Rápida de Backups

## Instalación Inicial

### 1. Verificar que los scripts existen

```bash
# Los scripts ya están creados:
ls -la compose/production/django/backup_media.sh
ls -la compose/production/django/restore_media.sh
ls -la compose/production/django/scheduled_backup.sh
```

### 2. Dar permisos de ejecución

```bash
chmod +x compose/production/django/backup_media.sh
chmod +x compose/production/django/restore_media.sh
chmod +x compose/production/django/scheduled_backup.sh
```

### 3. Reconstruir las imágenes Docker

```bash
# Local
just build
just up

# Producción (cuando hagas deploy)
just deploy-production
```

### 4. Verificar que funciona

```bash
# Local
just backup-full
just list-backups

# Producción
just production-backup-full
just production-list-backups
```

## Uso Diario

### Crear Backups

```bash
# Producción - Backup completo
just production-backup-full

# Producción - Solo DB
just production-backup-db

# Producción - Solo media
just production-backup-media
```

### Ver Backups

```bash
just production-list-backups
```

### Descargar Backups a tu Máquina

```bash
# Descargar DB
just production-download-backup postgres backup_2024_01_15T14_30_00.sql.gz

# Descargar media
just production-download-backup media production_media_backup_2024_01_15T14_30_00.tar.gz

# Los backups se guardan en:
# - Base de datos: ./backups/ (raíz)
# - Archivos media: ./backups/media/
```

## Configurar Backups Automáticos

### En el servidor de producción

```bash
# 1. SSH al servidor
ssh $SSH_MARTINA_USER_AND_IP

# 2. Ir al directorio del proyecto
cd app-martina-production

# 3. Dar permisos al script
chmod +x compose/production/django/scheduled_backup.sh

# 4. Configurar cron
crontab -e

# Añadir estas líneas:
0 2 * * * $HOME/app-martina-production/compose/production/django/scheduled_backup.sh
0 3 * * 0 $HOME/app-martina-production/compose/production/django/scheduled_backup.sh

# 5. Guardar y salir

# 6. Verificar
crontab -l
```

## Restaurar

### Restaurar Base de Datos

```bash
# 1. Listar backups
just production-list-backups

# 2. Restaurar (requiere escribir "SI" para confirmar)
just production-restore-db backup_2024_01_15T14_30_00.sql.gz
```

### Restaurar Archivos Media

```bash
# 1. Listar backups
just production-list-backups

# 2. Restaurar (requiere escribir "SI" para confirmar)
just production-restore-media media_backup_2024_01_15T14_30_00.tar.gz
```

## Comandos Útiles

```bash
# Ver tamaño de los backups
ssh $SSH_MARTINA_USER_AND_IP "du -sh ~/app-martina-production/backups/*"

# Ver espacio disponible
ssh $SSH_MARTINA_USER_AND_IP "df -h"

# Ver log de backups
ssh $SSH_MARTINA_USER_AND_IP "tail -n 50 ~/app-martina-production/backups/backup.log"
```

## Checklist Mensual

- [ ] Verificar backups automáticos: `crontab -l`
- [ ] Revisar logs: `cat ~/app-martina-production/backups/backup.log`
- [ ] Verificar espacio: `df -h`
- [ ] Descargar backup reciente a local
- [ ] Probar restaurar en desarrollo

---

**💡 Tip**: Descarga backups semanalmente a tu máquina local como seguridad extra.
