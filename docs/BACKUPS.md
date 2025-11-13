# Sistema de Copias de Seguridad

Este documento describe el sistema completo de copias de seguridad implementado para la aplicación Martina Bescós.

## 📋 Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Qué se respalda](#qué-se-respalda)
- [Comandos Disponibles](#comandos-disponibles)
- [Configuración Automática](#configuración-automática)
- [Restauración](#restauración)
- [Mejores Prácticas](#mejores-prácticas)
- [Troubleshooting](#troubleshooting)

## 📦 Descripción General

El sistema de backups está diseñado para proteger:
- **Base de datos PostgreSQL**: Todas las tablas y datos
- **Archivos media**: Imágenes, documentos, videos, PDFs

Los backups se almacenan en volúmenes Docker persistentes y están disponibles tanto en local como en producción.

## 🎯 Qué se respalda

### Base de Datos
- **Formato**: SQL comprimido con gzip (`*.sql.gz`)
- **Ubicación**: `/backups/` (volumen Docker)
- **Retención**: Todos los backups se mantienen (limpieza manual)
- **Nomenclatura**: `backup_YYYY_MM_DDTHH_MM_SS.sql.gz`

### Archivos Media
- **Formato**: Tarball comprimido (`*.tar.gz`)
- **Ubicación**: `/backups/media/` (volumen Docker)
- **Retención**: 30 días (limpieza automática)
- **Nomenclatura**: `media_backup_YYYY_MM_DDTHH_MM_SS.tar.gz`

## 🚀 Comandos Disponibles

### Entorno Local

```bash
# Crear backup de base de datos
just backup-db

# Crear backup de archivos media
just backup-media

# Crear backup completo (DB + media)
just backup-full

# Listar backups disponibles
just list-backups

# Restaurar base de datos
just restore-db backup_2024_01_15T14_30_00.sql.gz

# Restaurar archivos media
just restore-media media_backup_2024_01_15T14_30_00.tar.gz
```

### Entorno de Producción

```bash
# Crear backup de base de datos
just production-backup-db

# Crear backup de archivos media
just production-backup-media

# Crear backup completo (DB + media)
just production-backup-full

# Listar backups disponibles
just production-list-backups

# Restaurar base de datos (con confirmación)
just production-restore-db backup_2024_01_15T14_30_00.sql.gz

# Restaurar archivos media (con confirmación)
just production-restore-media media_backup_2024_01_15T14_30_00.tar.gz

# Descargar backup desde producción a local
just production-download-backup postgres backup_2024_01_15T14_30_00.sql.gz
just production-download-backup media media_backup_2024_01_15T14_30_00.tar.gz
```

## ⏰ Configuración Automática

### Configurar Backups Programados en Producción

1. **Conectar al servidor**:
```bash
ssh $SSH_MARTINA_USER_AND_IP
cd app-martina-production
```

2. **Verificar que el script existe**:
```bash
ls -la compose/production/django/scheduled_backup.sh
```

3. **Dar permisos de ejecución**:
```bash
chmod +x compose/production/django/scheduled_backup.sh
```

4. **Configurar crontab**:
```bash
crontab -e
```

Añadir las siguientes líneas (copia desde `compose/production/crontab`):
```cron
# Backup diario a las 2:00 AM
0 2 * * * $HOME/app-martina-production/compose/production/django/scheduled_backup.sh

# Backup semanal extra los domingos a las 3:00 AM
0 3 * * 0 $HOME/app-martina-production/compose/production/django/scheduled_backup.sh

# Limpieza de logs antiguos (90 días)
0 4 1 * * find $HOME/app-martina-production/backups -name "backup.log.*" -mtime +90 -delete
```

5. **Verificar que cron está funcionando**:
```bash
# Ver el crontab actual
crontab -l

# Ver logs de cron (puede variar según sistema)
grep CRON /var/log/syslog | tail -n 20

# Ver logs de backup
tail -f ~/app-martina-production/backups/backup.log
```

## 🔄 Restauración

### Restaurar desde Backup Local

```bash
# 1. Listar backups disponibles
just production-list-backups

# 2. Restaurar base de datos
just production-restore-db backup_2024_01_15T14_30_00.sql.gz

# 3. Restaurar archivos media
just production-restore-media media_backup_2024_01_15T14_30_00.tar.gz
```

### Restaurar en un Nuevo Servidor

```bash
# 1. Clonar el repositorio
git clone <repo-url> app-martina-production
cd app-martina-production

# 2. Configurar variables de entorno
mkdir -p .envs/.production
# Copiar archivos .django y .postgres desde backup seguro

# 3. Copiar backups al servidor
scp ./backups/production_backup_*.sql.gz user@server:~/app-martina-production/backups/
scp ./backups/production_media_backup_*.tar.gz user@server:~/app-martina-production/backups/media/

# 4. Iniciar contenedores
docker compose -f docker-compose.production.yml up -d

# 5. Restaurar base de datos
docker compose -f docker-compose.production.yml exec postgres restore backup_2024_01_15T14_30_00.sql.gz

# 6. Restaurar media
docker compose -f docker-compose.production.yml run --rm django /restore_media.sh media_backup_2024_01_15T14_30_00.tar.gz

# 7. Aplicar migraciones pendientes (si hay)
docker compose -f docker-compose.production.yml run --rm django python manage.py migrate
```

## ✅ Mejores Prácticas

### Frecuencia de Backups

- **Producción**: Diario (2:00 AM) + Semanal extra (domingo 3:00 AM)
- **Staging**: Semanal
- **Desarrollo**: Bajo demanda

### Retención

- **Base de datos**: Mantener backups manualmente (no hay limpieza automática)
- **Archivos media**: 30 días (limpieza automática)

### Verificación Mensual

```bash
# 1. Verificar que los backups se están creando
just production-list-backups

# 2. Descargar un backup reciente
just production-download-backup postgres backup_YYYY_MM_DD.sql.gz

# 3. Restaurar en entorno de desarrollo para probar
just restore-db backup_YYYY_MM_DD.sql.gz

# 4. Verificar espacio en disco
ssh $SSH_MARTINA_USER_AND_IP "df -h"
```

### Monitoreo

1. **Revisar logs regularmente**:
```bash
ssh $SSH_MARTINA_USER_AND_IP "tail -f ~/app-martina-production/backups/backup.log"
```

2. **Verificar espacio en disco**:
```bash
ssh $SSH_MARTINA_USER_AND_IP "docker compose -f app-martina-production/docker-compose.production.yml exec django df -h /backups"
```

## 🔧 Troubleshooting

### Error: "No space left on device"

```bash
# Ver espacio disponible
df -h

# Limpiar backups antiguos de base de datos manualmente
ssh $SSH_MARTINA_USER_AND_IP
cd app-martina-production
docker compose -f docker-compose.production.yml exec postgres bash
cd /backups
# Ver backups
ls -lh
# Eliminar backups antiguos
rm backup_2023_*.sql.gz

# Limpiar backups de media antiguos manualmente (si es necesario)
docker compose -f docker-compose.production.yml exec django find /backups/media -name "media_backup_*.tar.gz" -mtime +60 -delete

# Limpiar imágenes Docker no usadas
docker system prune -a
```

### Error: "Permission denied"

```bash
# Verificar permisos del volumen
docker compose -f docker-compose.production.yml exec django ls -la /backups

# Ajustar permisos si es necesario
docker compose -f docker-compose.production.yml exec django chmod -R 755 /backups
```

### Backup muy lento

```bash
# Verificar tamaño de los datos
docker compose -f docker-compose.production.yml exec django du -sh /app/martina_bescos_app/media

# Ver archivos más grandes
docker compose -f docker-compose.production.yml exec django find /app/martina_bescos_app/media -type f -size +100M -ls
```

### No se puede restaurar el backup

```bash
# Verificar integridad del archivo
gzip -t /ruta/al/backup.sql.gz

# Verificar que el tarball no está corrupto
tar -tzf /ruta/al/media_backup.tar.gz | head

# Ver el contenido sin extraer
tar -tzf /ruta/al/media_backup.tar.gz | less
```

### Cron no está ejecutando los backups

```bash
# Verificar que cron está corriendo
systemctl status cron

# Ver logs de cron
grep CRON /var/log/syslog | tail -n 50

# Verificar que el script tiene permisos
ls -la ~/app-martina-production/compose/production/django/scheduled_backup.sh

# Probar el script manualmente
~/app-martina-production/compose/production/django/scheduled_backup.sh

# Ver variables de entorno de cron
crontab -l
```

## 📊 Estructura de Directorios

```
/backups/
├── postgres/
│   ├── backup_2024_01_15T14_30_00.sql.gz
│   ├── backup_2024_01_16T14_30_00.sql.gz
│   └── ...
├── media/
│   ├── media_backup_2024_01_15T14_30_00.tar.gz
│   ├── media_backup_2024_01_16T14_30_00.tar.gz
│   └── temp_before_restore_*.tar.gz  # Backups temporales al restaurar
└── backup.log              # Log de backups automáticos
```

## 🔐 Seguridad

### Backups de Variables de Entorno

Las variables de entorno **NO se incluyen** en los backups automáticos. Debes mantener copias seguras de:

```
.envs/.production/.django
.envs/.production/.postgres
```

Recomendación: Usa un gestor de contraseñas (1Password, Bitwarden, etc.) para guardar estos archivos.

### Acceso a Backups

Los backups se almacenan en volúmenes Docker. Solo usuarios con acceso SSH al servidor pueden acceder a ellos:

```bash
# Ver backups
ssh $SSH_MARTINA_USER_AND_IP "ls -la ~/app-martina-production/backups"
```

### Copias Externas

Es recomendable descargar backups periódicamente a tu máquina local:

```bash
# Descargar backups mensuales
just production-download-backup postgres backup_2024_01_01T02_00_00.sql.gz
just production-download-backup media media_backup_2024_01_01T02_00_00.tar.gz

# Guardarlos en ubicación segura (externa al proyecto)
```

## 🚀 Roadmap / TODOs

### Pendientes de Implementación

- [ ] **Configurar Cron para Backups Automáticos**
  - Instalar cron en stage (backups diarios a las 2:00 AM)
  - Instalar cron en production (backups diarios + semanales)
  - Opcionalmente añadir limpieza automática para PostgreSQL (ej: mantener últimos 90 días)
  - Archivo de ejemplo: `compose/production/crontab`

- [ ] **Integración con Healthchecks.io**
  - Configurar monitoreo de backups con [healthchecks.io](https://healthchecks.io/)
  - Enviar ping al inicio y fin de cada backup
  - Alertas por email/Slack si un backup falla
  - Detectar backups que no se ejecutaron
  - Dashboard de estado de backups

### Mejoras Futuras

- [ ] Añadir limpieza automática para backups de PostgreSQL (actualmente infinitos)
- [ ] Implementar verificación de integridad de backups
- [ ] Backup incremental para archivos media (actualmente siempre completo)
- [ ] Compresión adicional con zstd en lugar de gzip
- [ ] Estadísticas de backups (tamaño, tiempo de ejecución)

## 📞 Soporte

Para problemas o preguntas sobre el sistema de backups:

1. Revisar los logs: `~/app-martina-production/backups/backup.log`
2. Consultar esta documentación
3. Revisar los scripts en `compose/production/django/`

---

**Última actualización**: 2024-11-13
