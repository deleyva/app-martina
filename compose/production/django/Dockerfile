# define an alias for the specific python version used in this file.
FROM docker.io/python:3.12.8-slim-bookworm AS python

# Python build stage
FROM python AS python-build-stage

ARG BUILD_ENVIRONMENT=production

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg dependencies
  libpq-dev


# Requirements are installed here to ensure they will be cached.
COPY ./requirements .

# Create Python Dependency and Sub-Dependency Wheels.
RUN pip wheel --wheel-dir /usr/src/app/wheels  \
  -r ${BUILD_ENVIRONMENT}.txt


# Node.js build stage for processing CSS
FROM node:16-slim AS node-build-stage

WORKDIR /app

# Create a basic package.json file
RUN echo '{"name":"martina-bescos-app","version":"1.0.0","scripts":{"build":"tailwindcss -i ./static/css/index.css -o ./static/css/output.css --minify"}}' > package.json

# Install dependencies locally instead of globally
RUN npm install tailwindcss postcss autoprefixer daisyui

# Copy CSS files
COPY ./martina_bescos_app/static/css ./static/css/

# Create empty output.css file as fallback
RUN touch ./static/css/output.css

# Try to process CSS with npm run build (using local tailwindcss)
# If it fails, we'll still have the empty output.css file
RUN npm run build || echo "Tailwind build failed, proceeding with empty CSS file"


# Python 'run' stage
FROM python AS python-run-stage

ARG BUILD_ENVIRONMENT=production
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN addgroup --system django \
  && adduser --system --ingroup django django


# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # entrypoint
  wait-for-it \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# All absolute dir copies ignore workdir instruction. All relative dir copies are wrt to the workdir instruction
# copy python dependency wheels from python-build-stage
COPY --from=python-build-stage /usr/src/app/wheels  /wheels/

# use wheels to install python dependencies
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
  && rm -rf /wheels/

# Copy processed CSS from Node.js stage
COPY --from=node-build-stage /app/static/css/output.css ${APP_HOME}/martina_bescos_app/static/css/


COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint


COPY --chown=django:django ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start


# copy application code to WORKDIR
COPY --chown=django:django . ${APP_HOME}

# make django owner of the WORKDIR directory as well.
RUN chown -R django:django ${APP_HOME}

# Run collectstatic before starting
RUN DJANGO_SETTINGS_MODULE=config.settings.production \
  DJANGO_SECRET_KEY=collectstatic_only \
  DJANGO_ADMIN_URL="admin-collectstatic-url/" \
  DATABASE_URL="postgres://postgres:postgres@postgres:5432/postgres" \
  python manage.py collectstatic --noinput

USER django

RUN DATABASE_URL="" \
  DJANGO_SETTINGS_MODULE="config.settings.test" \
  python manage.py compilemessages

ENTRYPOINT ["/entrypoint"]
