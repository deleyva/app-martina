export COMPOSE_FILE := "docker-compose.local.yml"

## Just does not yet manage signals for subprocesses reliably, which can lead to unexpected behavior.
## Exercise caution before expanding its usage in production environments. 
## For more information, see https://github.com/casey/just/issues/2473 .


# Default command to list all available commands.
default:
    @just --list

# build: Build python image.
build:
    @echo "Building python image..."
    @docker compose build

# up: Start up containers.
up:
    @echo "Starting up containers..."
    @docker compose up -d --remove-orphans

# up: Start up containers, not in detached mode
updev:
    @echo "Starting up containers..."
    @docker compose up --remove-orphans

# down: Stop containers.
down:
    @echo "Stopping containers..."
    @docker compose down

# prune: Remove containers and their volumes.
prune *args:
    @echo "Killing containers and removing volumes..."
    @docker compose down -v {{args}}

# logs: View container logs
logs *args:
    @docker compose logs -f {{args}}

# manage: Executes `manage.py` command.
manage +args:
    @docker compose run --rm django python ./manage.py {{args}}

# test: Run tests.
test:
    @docker compose run --rm django pytest

# run a python command
command +args:
    @docker compose run --rm django {{args}}

# start an interactive terminal
django-shell:
    @docker compose run --rm django python ./manage.py shell

stage-create-superuser:
    @echo "INFO: Intentando crear superusuario en staging ($SSH_MARTINA_USER_AND_IP)..."
    # Usamos 'ssh -t' para forzar TTY. Usamos 'docker compose run' para asegurar variables de entorno Y permitir interactividad.
    @ssh -t $SSH_MARTINA_USER_AND_IP "cd ~/app-martina-stage && \
        echo 'INFO: Ejecutando createsuperuser dentro de un contenedor Docker temporal...' && \
        docker compose -f docker-compose.stage.yml run --rm django python ./manage.py createsuperuser"
    @echo "INFO: Proceso de creación de superusuario finalizado."

# stage-manage: Executes `manage.py` command in stage environment.
stage-manage +args:
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml run --rm django python ./manage.py {{args}}"

deploybuildpre:
	ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-pre && \
	git stash && \
	git pull && \
	git stash clear && \
	docker compose -f docker-compose.stage.yml down && \
	docker compose -f docker-compose.stage.yml up"

# deploy-stage: Deploy to stage environment
deploy-stage:
	@echo "Deploying to stage environment..."
	# Create necessary directories if they don't exist
	ssh $SSH_MARTINA_USER_AND_IP "mkdir -p app-martina-stage/.envs/.production"
	
	# Copy environment files that are not in version control
	scp ./.envs/.production/.django $SSH_MARTINA_USER_AND_IP:app-martina-stage/.envs/.production/
	scp ./.envs/.production/.postgres $SSH_MARTINA_USER_AND_IP:app-martina-stage/.envs/.production/
	
	# Deploy the application
	ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
	git reset --hard && \
	git fetch origin && \
	git checkout -f main && \
	git reset --hard origin/main && \
	docker compose -f docker-compose.stage.yml down && \
	docker compose -f docker-compose.stage.yml build && \
	docker compose -f docker-compose.stage.yml up -d && \
	echo 'Esperando a que los servicios estén listos...' && \
	sleep 10 && \
	echo 'Aplicando migraciones...' && \
	docker compose -f docker-compose.stage.yml run --rm django python manage.py migrate"

# deploy-production: Deploy to production environment
deploy-production:
	@echo "Deploying to production environment..."
	# Create necessary directories if they don't exist
	ssh $SSH_MARTINA_USER_AND_IP "mkdir -p app-martina-production/.envs/.production"
	
	# Copy environment files that are not in version control
	scp ./.envs/.production/.django $SSH_MARTINA_USER_AND_IP:app-martina-production/.envs/.production/
	scp ./.envs/.production/.postgres $SSH_MARTINA_USER_AND_IP:app-martina-production/.envs/.production/
	
	# Deploy the application
	ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
	git reset --hard && \
	git fetch origin && \
	git checkout -f main && \
	git reset --hard origin/main && \
	docker compose -f docker-compose.production.yml down && \
	docker compose -f docker-compose.production.yml build && \
	docker compose -f docker-compose.production.yml up -d && \
	echo 'Esperando a que los servicios estén listos...' && \
	sleep 10 && \
	echo 'Aplicando migraciones...' && \
	docker compose -f docker-compose.production.yml run --rm django python manage.py migrate"

# production-manage: Executes `manage.py` command in production environment.
production-manage +args:
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml run --rm django python ./manage.py {{args}}"

# production-create-superuser: Creates a superuser in production environment.
production-create-superuser:
    @echo "INFO: Intentando crear superusuario en producción ($SSH_MARTINA_USER_AND_IP)..."
    # Usamos 'ssh -t' para forzar TTY. Usamos 'docker compose run' para asegurar variables de entorno Y permitir interactividad.
    @ssh -t $SSH_MARTINA_USER_AND_IP "cd ~/app-martina-production && \
        echo 'INFO: Ejecutando createsuperuser dentro de un contenedor Docker temporal...' && \
        docker compose -f docker-compose.production.yml run --rm django python ./manage.py createsuperuser"
    @echo "INFO: Proceso de creación de superusuario finalizado."

# migrations: Creates new migrations.
migrations:
    @echo "Creating new migrations..."
    @docker compose run --rm django python ./manage.py makemigrations

# migrate: Applies migrations.
migrate *args:
    @echo "Applying migrations..."
    @docker compose run --rm django python ./manage.py migrate {{args}}

# create django app
createapp +args:
    @echo "Creating new django app..."
    @docker compose run --rm django python ./manage.py startapp {{args}}

# =============================================================================
# BACKUP COMMANDS
# =============================================================================

# backup: Create a database backup (local)
backup-db:
    @echo "Creating database backup..."
    @docker compose exec postgres backup

# backup-media: Create a media files backup (local)
backup-media:
    @echo "Creating media files backup..."
    @docker compose run --rm django /backup_media.sh

# backup-full: Create a complete backup (database + media) (local)
backup-full:
    @echo "Creating complete backup..."
    @just backup-db
    @just backup-media

# list-backups: List available backups (local)
list-backups:
    @echo "Database backups:"
    @docker compose exec postgres backups
    @echo "\nMedia backups:"
    @docker compose exec django ls -lh /backups/media 2>/dev/null || echo "No media backups found"

# restore-db: Restore database from backup (local)
restore-db backup_file:
    @echo "Restoring database from {{backup_file}}..."
    @docker compose exec postgres restore {{backup_file}}

# restore-media: Restore media files from backup (local)
restore-media backup_file:
    @echo "Restoring media files from {{backup_file}}..."
    @docker compose run --rm django /restore_media.sh {{backup_file}}

# production-backup-db: Create a database backup (production)
production-backup-db:
    @echo "Creating production database backup..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml exec postgres backup"

# production-backup-media: Create a media files backup (production)
production-backup-media:
    @echo "Creating production media backup..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml run --rm django /backup_media.sh"

# production-backup-full: Create a complete backup (database + media) (production)
production-backup-full:
    @echo "Creating complete production backup..."
    @just production-backup-db
    @just production-backup-media

# production-list-backups: List available backups (production)
production-list-backups:
    @echo "Production database backups:"
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml exec postgres backups"
    @echo "\nProduction media backups:"
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml exec django ls -lh /backups/media 2>/dev/null || echo 'No media backups found'"

# production-restore-db: Restore database from backup (production)
production-restore-db backup_file:
    @echo "⚠️  WARNING: This will restore production database from {{backup_file}}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml exec postgres restore {{backup_file}}"

# production-restore-media: Restore media files from backup (production)
production-restore-media backup_file:
    @echo "⚠️  WARNING: This will restore production media files from {{backup_file}}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml run --rm django /restore_media.sh {{backup_file}}"

# production-download-backup: Download a backup from production to local machine
production-download-backup backup_type backup_file:
    @echo "Downloading {{backup_type}} backup: {{backup_file}}"
    @mkdir -p ./backups/{{backup_type}}
    @scp $SSH_MARTINA_USER_AND_IP:app-martina-production/backups/{{backup_type}}/{{backup_file}} ./backups/{{backup_type}}/
    @echo "✓ Downloaded to ./backups/{{backup_type}}/{{backup_file}}"

# stage-backup-db: Create a database backup (stage)
stage-backup-db:
    @echo "Creating stage database backup..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml exec postgres backup"

# stage-backup-media: Create a media files backup (stage)
stage-backup-media:
    @echo "Creating stage media backup..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml run --rm django /backup_media.sh"

# stage-backup-full: Create a complete backup (database + media) (stage)
stage-backup-full:
    @echo "Creating complete stage backup..."
    @just stage-backup-db
    @just stage-backup-media

# stage-list-backups: List available backups (stage)
stage-list-backups:
    @echo "Stage database backups:"
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml exec postgres backups"
    @echo "\nStage media backups:"
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml exec django ls -lh /backups/media 2>/dev/null || echo 'No media backups found'"

# stage-restore-db: Restore database from backup (stage)
stage-restore-db backup_file:
    @echo "⚠️  WARNING: This will restore stage database from {{backup_file}}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml exec postgres restore {{backup_file}}"

# stage-restore-media: Restore media files from backup (stage)
stage-restore-media backup_file:
    @echo "⚠️  WARNING: This will restore stage media files from {{backup_file}}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml run --rm django /restore_media.sh {{backup_file}}"

# stage-download-backup: Download a backup from stage to local machine
stage-download-backup backup_type backup_file:
    @echo "Downloading {{backup_type}} backup from stage: {{backup_file}}"
    @mkdir -p ./backups/{{backup_type}}
    @scp $SSH_MARTINA_USER_AND_IP:app-martina-stage/backups/{{backup_type}}/{{backup_file}} ./backups/{{backup_type}}/
    @echo "✓ Downloaded to ./backups/{{backup_type}}/{{backup_file}}"
