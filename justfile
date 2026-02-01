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

# print-env: Print environment variables inside a running container.
# Usage: just print-env [service] [VAR...]
print-env service *vars:
    @docker compose exec {{service}} printenv {{vars}}

# print-env-django: Convenience shortcut for the django container.
# Usage: just print-env-django [VAR...]
print-env-django *vars:
    @docker compose exec django printenv {{vars}}

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

# production-logs: View production Django logs in real-time
production-logs:
    @echo "Connecting to production logs..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml logs -f django --tail=50"

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

# production-backup-db: Create a database backup and keep only 2 most recent (production)
production-backup-db:
    @echo "Creating production database backup..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml exec postgres backup"
    @echo "🧹 Cleaning old DB backups (keeping 2 most recent)..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production/backups && \
    ls -t *.sql.gz 2>/dev/null | tail -n +3 | xargs -r rm -v || echo 'No old DB backups to remove'"

# production-backup-media: Create a media files backup and keep only 2 most recent (production)
production-backup-media:
    @echo "Creating production media backup..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml run --rm django /backup_media.sh"
    @echo "🧹 Cleaning old media backups (keeping 2 most recent)..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production/backups/media && \
    ls -t *.tar.gz 2>/dev/null | tail -n +3 | xargs -r rm -v || echo 'No old media backups to remove'"

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

# production-delete-backup-db: Delete a specific database backup (production)
production-delete-backup-db backup_file:
    @echo "⚠️  WARNING: This will DELETE production database backup: {{backup_file}}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && rm -f backups/{{backup_file}}"
    @echo "✓ Deleted {{backup_file}}"

# production-delete-backup-media: Delete a specific media backup (production)
production-delete-backup-media backup_file:
    @echo "⚠️  WARNING: This will DELETE production media backup: {{backup_file}}"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && rm -f backups/media/{{backup_file}}"
    @echo "✓ Deleted {{backup_file}}"

# production-cleanup-backups: Keep only the 2 most recent backups of each type (production)
production-cleanup-backups:
    @echo "🧹 Cleaning up old backups, keeping only 2 most recent..."
    @echo "\n📦 Database backups cleanup:"
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production/backups && \
    ls -t *.sql.gz 2>/dev/null | tail -n +3 | xargs -r rm -v || echo 'No old DB backups to remove'"
    @echo "\n📁 Media backups cleanup:"
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production/backups/media && \
    ls -t *.tar.gz 2>/dev/null | tail -n +3 | xargs -r rm -v || echo 'No old media backups to remove'"
    @echo "\n✓ Cleanup complete"

# vps-docker-prune: Clean up Docker system (images, build cache) - safe for shared VPS (stage + production)
vps-docker-prune:
    @echo "⚠️  WARNING: This will remove unused Docker images and build cache"
    @echo "   (Volumes are preserved to protect stage and production data)"
    @echo "Press Ctrl+C to cancel, or Enter to continue..."
    @read
    @ssh $SSH_MARTINA_USER_AND_IP "docker image prune -af && docker builder prune -af"
    @echo "✓ Docker cleanup complete (images + build cache)"

# vps-docker-prune-full: Full Docker cleanup INCLUDING volumes - USE WITH CAUTION
# vps-docker-prune-full:
#     @echo "🚨 DANGER: This will remove ALL unused Docker data INCLUDING VOLUMES"
#     @echo "   This affects BOTH stage AND production on your shared VPS!"
#     @echo "   Make sure you have backups before proceeding."
#     @echo "Press Ctrl+C to cancel, or Enter to continue..."
#     @read
#     @ssh $SSH_MARTINA_USER_AND_IP "docker system prune -af --volumes"
#     @echo "✓ Full Docker cleanup complete"

# production-disk-usage: Check disk usage on production server
production-disk-usage:
    @echo "📊 Production server disk usage:"
    @ssh $SSH_MARTINA_USER_AND_IP "df -h && echo '\n📦 Docker disk usage:' && docker system df"

# production-download-backup: Download a backup from production to local machine
# Usage: just production-download-backup postgres production_backup_2025_11_13.sql.gz
#        just production-download-backup media production_media_backup_2025_11_13.tar.gz
production-download-backup backup_type backup_file:
    @echo "Downloading {{backup_type}} backup: {{backup_file}}"
    @mkdir -p ./backups/
    @if [ "{{backup_type}}" = "postgres" ]; then \
        scp $SSH_MARTINA_USER_AND_IP:app-martina-production/backups/{{backup_file}} ./backups/; \
    else \
        scp $SSH_MARTINA_USER_AND_IP:app-martina-production/backups/media/{{backup_file}} ./backups/; \
    fi
    @echo "✓ Downloaded to ./backups/{{backup_file}}"

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
# Usage: just stage-download-backup postgres backup_2025_11_13.sql.gz
#        just stage-download-backup media media_backup_2025_11_13.tar.gz
stage-download-backup backup_type backup_file:
    @echo "Downloading {{backup_type}} backup from stage: {{backup_file}}"
    @mkdir -p ./backups/
    @if [ "{{backup_type}}" = "postgres" ]; then \
        scp $SSH_MARTINA_USER_AND_IP:app-martina-stage/backups/{{backup_file}} ./backups/; \
    else \
        scp $SSH_MARTINA_USER_AND_IP:app-martina-stage/backups/media/{{backup_file}} ./backups/; \
    fi
    @echo "✓ Downloaded to ./backups/{{backup_file}}"

# =============================================================================
# AI METADATA DIAGNOSTIC COMMANDS
# =============================================================================

# test-ai-metadata: Test AI metadata extraction locally
test-ai-metadata:
    @echo "Testing AI metadata extraction locally..."
    @docker compose run --rm django python ./manage.py test_ai_metadata

# test-ai-metadata-custom: Test AI metadata extraction with custom input (local)
# Usage: just test-ai-metadata-custom "Partitura de Extremoduro - So Payaso"
test-ai-metadata-custom description:
    @echo "Testing AI metadata extraction with custom description..."
    @docker compose run --rm django python ./manage.py test_ai_metadata --description "{{description}}"

# stage-test-ai-metadata: Test AI metadata extraction in staging
stage-test-ai-metadata:
    @echo "Testing AI metadata extraction in staging..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-stage && \
    docker compose -f docker-compose.stage.yml run --rm django python ./manage.py test_ai_metadata"

# production-test-ai-metadata: Test AI metadata extraction in production
production-test-ai-metadata:
    @echo "Testing AI metadata extraction in production..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml run --rm django python ./manage.py test_ai_metadata"

# production-logs-ai: View AI-related logs in production (last 100 lines)
production-logs-ai:
    @echo "Fetching AI-related logs from production..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml logs --tail=100 django | grep -i 'ai\|gemini\|metadata'"

# production-check-env-gemini: Check if GEMINI_API_KEY is configured in production
production-check-env-gemini:
    @echo "Checking GEMINI_API_KEY configuration in production..."
    @ssh $SSH_MARTINA_USER_AND_IP "cd app-martina-production && \
    docker compose -f docker-compose.production.yml exec django printenv | grep GEMINI || echo '❌ GEMINI_API_KEY not found'"
