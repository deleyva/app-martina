# syntax=docker/dockerfile:1

# --- Python Base ---
FROM docker.io/python:3.12.8-slim-bookworm AS python

# --- Node.js Builder ---
FROM docker.io/node:18 AS node-builder
WORKDIR /app/frontend
COPY package.json package-lock.json* ./
RUN npm install
COPY . /app/frontend/
RUN npm run build -- --minify # Asegúrate de que tu script build minifique

# --- Python Build Stage (Wheels) ---
FROM python AS python-build-stage
ARG BUILD_ENVIRONMENT=production
RUN apt-get update && apt-get install --no-install-recommends -y \
  build-essential \
  libpq-dev \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*
COPY ./requirements .
RUN pip wheel --wheel-dir /usr/src/app/wheels \
  -r ${BUILD_ENVIRONMENT}.txt

# --- Python Run Stage (Final Image) ---
FROM python AS python-run-stage
ARG BUILD_ENVIRONMENT=production
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}
WORKDIR ${APP_HOME}

RUN addgroup --system django \
  && adduser --system --ingroup django django

RUN apt-get update && apt-get install --no-install-recommends -y \
  libpq-dev \
  gettext \
  wait-for-it \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

COPY --from=python-build-stage /usr/src/app/wheels /wheels/
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
  && rm -rf /wheels/

COPY ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copiar el código de la aplicación
COPY . ${APP_HOME}

# Copiar CSS compilado desde node-builder
COPY --from=node-builder /app/frontend/martina_bescos_app/static/css/output.css ${APP_HOME}/martina_bescos_app/static/css/output.css

# *** collectstatic YA NO SE EJECUTA AQUÍ ***

# Cambiar propietario de todo ANTES de cambiar de usuario
# Necesario para que collectstatic (ejecutado por 'django' user) pueda escribir en STATIC_ROOT si es necesario
RUN chown -R django:django ${APP_HOME}

# Cambiar al usuario no-root
USER django

ENTRYPOINT ["/entrypoint"]

# CMD ["/start"] # El comando se ejecuta desde el start script a través de entrypoint