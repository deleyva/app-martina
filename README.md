# Martina Bescós App

Plataforma open source para educación musical construida con Django y Wagtail. 

La aplicación combina varios módulos pensados para profesorado y alumnado de conservatorio/escuela de música:

- Biblioteca de partituras y recursos musicales.
- Filtros avanzados por etiquetas, categorías, dificultad, etc.
- Biblioteca personal del alumnado con visor optimizado para partituras (inspirado en forScore).
- Sistema de estudio con repetición espaciada para material musical.
- Herramientas de evaluación y gestión de grupos/clases.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Características principales

- **Biblioteca musical (Music Pills)** basada en Wagtail: partituras en PDF, metadatos ricos, categorías y tags.
- **Filtros avanzados de partituras** (`/scores/filtered/`) combinando etiquetas de documentos, tags de página, categorías y dificultad.
- **Mi Biblioteca** personal del usuario con visor de PDFs, imágenes y audio adaptado a práctica musical.
- **Music Cards**: sistema de repetición espaciada para estudiar material musical.
- **Gestión de clases y evaluaciones**: grupos, sesiones de clase y rúbricas de evaluación.
- **Autenticación con Google** usando `django-allauth`.


## Stack técnico

- **Backend**: Django + Wagtail CMS
- **Base de datos**: PostgreSQL
- **Frontend**: Tailwind CSS + DaisyUI, HTMX
- **Tareas asíncronas**: Huey + Redis (por ejemplo, para compresión de vídeo)
- **Auth**: django-allauth (login con Google)
- **Infraestructura**: Docker, orquestado mediante `docker compose` y `just`


## Puesta en marcha (local)

### Requisitos previos

- Docker y Docker Compose
- [`just`](https://github.com/casey/just) instalado en tu máquina

### 1. Clonar el repositorio

```bash
git clone https://github.com/deleyva/app-martina.git
cd app-martina
```

### 2. Variables de entorno

Configura los ficheros `.env` según tus necesidades (por ejemplo en `.envs/.local/`).

> Consulta los ejemplos incluidos en el proyecto para la configuración de Django, PostgreSQL y Redis.

### 3. Construir y levantar los contenedores

```bash
just build        # opcional: construye las imágenes
just up           # levanta los contenedores en segundo plano
```

Para desarrollo interactivo también puedes usar:

```bash
just updev        # levanta los contenedores en primer plano
```

### 4. Migraciones y superusuario

```bash
just migrate                      # aplica migraciones de base de datos
just manage createsuperuser       # crea un superusuario de Django
```

### 5. Acceso a la aplicación

- Aplicación principal: <http://localhost:8000/>
- Admin de Django: <http://localhost:8000/admin/>
- Admin de Wagtail: <http://localhost:8000/cms/>


## Tests

Para ejecutar la suite de tests:

```bash
just test
```

Puedes utilizar también los comandos estándar de `pytest` dentro del contenedor si lo necesitas.


## Estilo de código

- **Python**: [Black](https://github.com/psf/black) para el formateo.
- **Linting**: [Ruff](https://github.com/astral-sh/ruff).
- **Plantillas HTML**: [djhtml](https://github.com/rtts/djhtml).

Antes de abrir un PR, asegúrate de que el código está formateado y que los tests pasan.


## Contribuir

Las contribuciones son bienvenidas. Recomendaciones básicas:

1. Haz un fork del repositorio y crea una rama para tu cambio.
2. Intenta seguir la filosofía del proyecto: Django limpio, vistas finas y modelos con la lógica principal.
3. Ejecuta los tests (`just test`) antes de abrir el PR.
4. Describe claramente la motivación de tu cambio y cualquier decisión de diseño relevante.


## License

Este proyecto se distribuye bajo licencia **MIT**.

