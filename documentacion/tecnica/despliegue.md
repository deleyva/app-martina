# Despliegue

## Entornos

Tres ficheros de Compose: `docker-compose.local.yml`, `docker-compose.stage.yml` y `docker-compose.production.yml`. Producción usa gunicorn + whitenoise, PostgreSQL y Redis; el correo se gestiona con django-anymail.

## Proceso general

```bash
git pull
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml run --rm django python manage.py migrate
docker compose -f docker-compose.production.yml up -d
```

## Multi-sitio

El proyecto puede servir varios sitios Wagtail; hay utilidades de sincronización y comprobación (`sync_sites.py`, `check_sites.py`).

## Notas de migraciones históricas

- El refactor **multi-grupo** (modelo `Enrollment`) migra datos automáticamente desde `Student`; ver `DEPLOYMENT_MULTI_GROUP.md` en la raíz del repo para el runbook completo.
- Varias tablas conservan nombres `evaluations_*` por compatibilidad (los modelos viven en `clases`); no renombrar.

## Backups

Ver `docs/BACKUPS.md` y `docs/BACKUP_QUICK_START.md` en el repo (scripts en `backups/`).
