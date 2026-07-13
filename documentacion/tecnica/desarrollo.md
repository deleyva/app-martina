# Desarrollo local

El entorno local corre con **Docker Compose** y se maneja con [`just`](https://github.com/casey/just).

## Puesta en marcha

```bash
git clone git@github.com:deleyva/app-martina.git
cd app-martina
just build     # construir imágenes
just up        # levantar contenedores (detached)
just logs      # ver logs
```

Comandos útiles del `justfile`:

```bash
just updev             # levantar en primer plano
just down              # parar
just prune             # parar y borrar volúmenes
just manage <cmd>      # manage.py dentro del contenedor (migrate, shell, ...)
```

## Migraciones

```bash
just manage makemigrations
just manage migrate
```

## Tests

Configurados con pytest (`--ds=config.settings.test`, ver `pyproject.toml`):

```bash
just manage test           # o bien:
pytest clases/ programacion/
```

!!! warning "sqlite y migraciones"
    Una migración antigua de `cms` contiene SQL específico de Postgres, por lo que la suite no puede crear el esquema en sqlite con migraciones. Fuera de Docker usa `pytest --no-migrations`.

## Calidad de código

Ruff para lint/format, mypy con django-stubs, djlint para templates, pre-commit configurado. CSS con Tailwind (`package.json` incluye el build).

## Estructura de settings

`config/settings/{base,local,test,production}.py` (patrón cookiecutter-django), variables de entorno con django-environ (`.envs/`, `DATABASE_URL`, etc.).
