# Martina Bescós App


## Siguientes pasos

- [X] Hacer que la rubrica actulice el dato en el selector de puntos de cada targeta "pending" y que ese número se pueda seguir editando
- [X] Hacer que se pueda desclicar el checkbox de classroom
- [ ] Mostrar pendings como lista y que, al clicar se muestre la rúbrica y todo

Behold My Awesome Project!

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

License: MIT

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
