# Martina Bescós App

## 🎼 Sistema de Filtros Avanzados para Partituras

La aplicación incluye un sistema completo de filtros avanzados que permite buscar partituras por diferentes criterios.

### 🔍 **Acceso a los Filtros**

**URL Base:** `/scores/filtered/`

**Desde la interfaz:** Botón "Filtros Avanzados" en la página principal de la biblioteca musical.

### 📋 **Parámetros de Filtrado Disponibles**

#### **1. Etiquetas de Documentos (`document_tags`)**
Busca en las etiquetas de PDFs, Audios e Imágenes asociados a las partituras.

**Ejemplos:**
```
/scores/filtered/?document_tags=piano
/scores/filtered/?document_tags=piano,leadsheet
/scores/filtered/?document_tags=3/8,lectura-rítmica
```

#### **2. Etiquetas de Página (`tags`)**
Busca en las etiquetas asignadas directamente a la ScorePage.

**Ejemplos:**
```
/scores/filtered/?tags=ejercicios
/scores/filtered/?tags=escalas,arpegios
```

#### **3. Categorías (`categories`)**
Filtra por categorías de las ScorePages.

**Ejemplos:**
```
/scores/filtered/?categories=estudios
/scores/filtered/?categories=jazz,clásico
```

#### **4. Nivel de Dificultad (`difficulty`)**
Busca documentos con un nivel de dificultad específico.

**Valores disponibles:** `beginner`, `easy`, `intermediate`, `advanced`, `expert`

**Ejemplos:**
```
/scores/filtered/?difficulty=beginner
/scores/filtered/?difficulty=advanced
```

### 🔗 **Filtros Combinados**

Puedes combinar múltiples filtros para búsquedas más específicas:

```
/scores/filtered/?document_tags=piano&difficulty=intermediate
/scores/filtered/?categories=jazz&document_tags=leadsheet
/scores/filtered/?tags=ejercicios&difficulty=beginner&document_tags=3/8
```

### 🎯 **Casos de Uso Prácticos**

- **Profesor de piano:** `?document_tags=piano&difficulty=beginner`
- **Estudiante de jazz:** `?categories=jazz&document_tags=leadsheet`
- **Práctica de ritmo:** `?document_tags=3/8,lectura-rítmica`
- **Ejercicios avanzados:** `?tags=ejercicios&difficulty=advanced`

### 🔧 **Características Técnicas**

- **Búsqueda case-insensitive:** No importan mayúsculas/minúsculas
- **Múltiples etiquetas:** Separadas por comas
- **Paginación:** 12 resultados por página
- **Filtros activos:** Se muestran como badges en la interfaz
- **Sin resultados:** Página con sugerencias útiles

### 📊 **Tipos de Documentos Soportados**

- **📄 PDFs:** Partituras, ejercicios, métodos
- **🎵 Audios:** Grabaciones, ejemplos, acompañamientos  
- **🖼️ Imágenes:** Diagramas, fotos de instrumentos, notación

## Siguientes pasos

- [X] Hacer que la rubrica actulice el dato en el selector de puntos de cada targeta "pending" y que ese número se pueda seguir editando
- [X] Hacer que se pueda desclicar el checkbox de classroom
- [X] Mostrar pendings como lista y que, al clicar se muestre la rúbrica y todo
- [ ] Hacer que funcione gemini. De momento no lo hace
- [ ] Hacer que se pueda enviar el correo


Behold My Awesome Project!

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## Roadmap

### Refactorización Técnica

- [ ] **Renombrar tablas de base de datos**: Actualmente las tablas de la app `clases` usan nombres con prefijo `evaluations_*` (ej: `evaluations_group`, `evaluations_student`). En el futuro, migrar a nombres coherentes como `clases_group`, `clases_student`, etc.
- [ ] **Soporte multi-asignatura**: Actualmente un estudiante solo puede estar en un grupo (una asignatura). Implementar soporte para que un estudiante pueda estar en múltiples asignaturas simultáneamente mediante relación ManyToMany.

### Funcionalidades

- [ ] Integración completa de biblioteca de grupo con Wagtail CMS
- [ ] Sistema de permisos por asignatura
- [ ] Dashboard de profesor multi-asignatura
- [ ] Exportación de datos en formato Excel/PDF

## License

MIT

## Settings

Moved to [settings](https://cookiecutter-django.readthedocs.io/en/latest/1-getting-started/settings.html).

## Basic Commands

### Setting Up Your Users

- To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.

- To create a **superuser account**, use this command:

      $ python manage.py createsuperuser

For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.

### Type checks

Running type checks with mypy:

    $ mypy martina_bescos_app

### Test coverage

To run the tests, check your test coverage, and generate an HTML coverage report:

    $ coverage run -m pytest
    $ coverage html
    $ open htmlcov/index.html

#### Running tests with pytest

    $ pytest

### Live reloading and Frontend Development

The application is built with a modern frontend stack:

- **Tailwind CSS** for utility-first styling
- **HTMX** for AJAX, CSS Transitions, and WebSockets without writing JavaScript
- **Alpine.js** for lightweight interactivity directly in HTML markup

When developing with Docker, live reloading is automatically configured:

    $ docker-compose -f docker-compose.local.yml up

This will:
1. Watch for changes in your Python/Django files and reload the server
2. Watch for changes in Tailwind CSS configuration and recompile styles
3. Auto-reload your browser when template or CSS files change

If you want to work with the Tailwind configuration or build process, check out:

    $ docker-compose -f docker-compose.local.yml exec django npm run build
    $ docker-compose -f docker-compose.local.yml exec django npm run dev

For production builds, the CSS is automatically optimized and minified during the Docker build process.

### Email Server

In development, it is often nice to be able to see emails that are being sent from your application. For that reason local SMTP server [Mailpit](https://github.com/axllent/mailpit) with a web interface is available as docker container.

Container mailpit will start automatically when you will run all docker containers.
Please check [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/2-local-development/developing-locally-docker.html) for more details how to start all containers.

With Mailpit running, to view messages that are sent by your application, open your browser and go to `http://127.0.0.1:8025`

## Deployment

The following details how to deploy this application.

### Docker

See detailed [cookiecutter-django Docker documentation](https://cookiecutter-django.readthedocs.io/en/latest/3-deployment/deployment-with-docker.html).

## Resumen diario de lo trabajado


## Tareas Futuras - Mejoras Técnicas

### Tailwind Typography (Prose) - Revisión Pendiente

**Fecha de creación**: Noviembre 2025  
**Prioridad**: Media  

#### Problema Identificado:
Las plantillas de blog (`cms/templates/cms/blog_page.html`) actualmente usan CSS personalizado para el formateo de contenido rich text en lugar de utilizar Tailwind Typography (`@tailwindcss/typography` con clases `prose`).

#### Situación Actual:
- Se implementó CSS personalizado con la clase `.blog-content` para resolver problemas de formateo de encabezados H2, H3, etc.
- Los estilos funcionan correctamente pero no aprovechan las ventajas de Tailwind Typography.

#### Acción Requerida:
1. **Investigar** por qué las clases `prose` de Tailwind Typography no funcionaron inicialmente
2. **Verificar** si `@tailwindcss/typography` está correctamente instalado y configurado en `tailwind.config.js`
3. **Revisar** la configuración de Tailwind CSS para asegurar que el plugin Typography esté habilitado
4. **Migrar** de CSS personalizado a clases `prose` estándar de Tailwind cuando sea posible
5. **Beneficios esperados**:
   - Mejor consistencia con el ecosistema Tailwind
   - Menos CSS personalizado que mantener
   - Mejor soporte para temas y personalización
   - Estilos más robustos y probados

#### Archivos Afectados:
- `cms/templates/cms/blog_page.html` (CSS personalizado en `{% block extra_css %}`)
- `tailwind.config.js` (verificar configuración del plugin)
- Posiblemente otros archivos de configuración de frontend

#### Notas Técnicas:
El CSS personalizado actual funciona correctamente y usa variables CSS de DaisyUI, por lo que no es urgente, pero sería beneficioso para la mantenibilidad a largo plazo.

