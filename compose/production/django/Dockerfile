# syntax=docker/dockerfile:1

# --- Python Base ---
# define an alias for the specific python version used in this file.
FROM docker.io/python:3.12.8-slim-bookworm AS python

# --- Node.js Builder ---
# Nueva etapa para construir los assets de frontend
FROM docker.io/node:18 AS node-builder
WORKDIR /app/frontend
# Copiar solo los archivos necesarios para instalar dependencias de Node
COPY package.json package-lock.json* ./
# Instalar dependencias (incluyendo devDependencies para build)
RUN npm install
# Copiar el resto del código fuente necesario para la compilación de Tailwind
# (tailwind.config.js, plantillas HTML, archivos css de entrada, etc.)
COPY . /app/frontend/
# Ejecutar el script de build definido en package.json
# Esto genera output.css dentro del WORKDIR
RUN npm run build


# --- Python Build Stage (Wheels) ---
FROM python AS python-build-stage
ARG BUILD_ENVIRONMENT=production
# Instalar dependencias de compilación de Python
RUN apt-get update && apt-get install --no-install-recommends -y \
  build-essential \
  libpq-dev \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# Copiar archivos de requerimientos
COPY ./requirements .
# Crear wheels para las dependencias Python
RUN pip wheel --wheel-dir /usr/src/app/wheels \
  -r ${BUILD_ENVIRONMENT}.txt


# --- Python Run Stage (Final Image) ---
FROM python AS python-run-stage
ARG BUILD_ENVIRONMENT=production
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}
# Establecer WORKDIR temprano
WORKDIR ${APP_HOME}

# Crear usuario y grupo
RUN addgroup --system django \
  && adduser --system --ingroup django django

# Instalar dependencias del sistema para runtime
RUN apt-get update && apt-get install --no-install-recommends -y \
  libpq-dev \
  gettext \
  wait-for-it \
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# Copiar wheels de Python desde la etapa de build
COPY --from=python-build-stage /usr/src/app/wheels /wheels/
# Instalar dependencias Python usando wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ /wheels/* \
  && rm -rf /wheels/

# Copiar scripts de entrypoint y start (propiedad root inicialmente)
COPY ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

# Copiar el código de la aplicación
# Copiar como root primero para permitir la compilación de CSS y collectstatic
COPY . ${APP_HOME}

# *** NUEVO: Copiar CSS compilado desde node-builder ***
# Sobrescribe el output.css del código fuente con la versión compilada
COPY --from=node-builder /app/frontend/martina_bescos_app/static/css/output.css ${APP_HOME}/martina_bescos_app/static/css/output.css

# *** NUEVO: Ejecutar collectstatic durante el build ***
# Se ejecuta como root porque aún no hemos cambiado de usuario
RUN python manage.py collectstatic --noinput

# Compilar mensajes (si se necesita)
# Ejecutar como root o ajustar permisos si es necesario
# RUN DATABASE_URL="" DJANGO_SETTINGS_MODULE="config.settings.production" python manage.py compilemessages

# *** NUEVO: Cambiar propietario DESPUÉS de compilar/recopilar ***
# Asegúrate de que todo en /app pertenece al usuario django
RUN chown -R django:django ${APP_HOME}

# Cambiar al usuario no-root
USER django

# Punto de entrada (sin cambios)
ENTRYPOINT ["/entrypoint"]

# Comando por defecto (ahora solo inicia gunicorn)
# CMD ["/start"] # El comando se ejecuta desde el start script