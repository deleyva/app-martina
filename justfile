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

# migrations: Creates new migrations.
migrations:
    @echo "Creating new migrations..."
    @docker compose run --rm django python ./manage.py makemigrations

# migrate: Applies migrations.
migrate:
    @echo "Applying migrations..."
    @docker compose run --rm django python ./manage.py migrate

# create django app
createapp +args:
    @echo "Creating new django app..."
    @docker compose run --rm django python ./manage.py startapp {{args}}
