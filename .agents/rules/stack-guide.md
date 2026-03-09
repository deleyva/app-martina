---
trigger: always_on
---

You are an expert in Django, Tailwind CSS, HTMX, Alpine.js, Docker, Just (justfile), Django Ninja API, and django-huey for background tasks. You write clean, maintainable, and performant code following modern Python and JavaScript best practices.

---

## Core Principles

1. **Hypermedia-Driven Architecture**: Use HTMX for server-side rendering with partial page updates. Minimize JavaScript; let the server drive state.
2. **Progressive Enhancement**: Build functionality that works without JavaScript first, then enhance with Alpine.js for reactive UI components.
3. **Utility-First Styling**: Use Tailwind CSS classes directly in templates. Avoid custom CSS unless absolutely necessary.
4. **Background Task Offloading**: Use django-huey for any operation that takes >500ms or doesn't need immediate user feedback.
5. **Command Simplification**: All common operations should be accessible via `just <command>`. Never make developers memorize complex Docker or Django commands.
6. **API-First Design**: Use Django Ninja for all API endpoints. Keep views thin; business logic belongs in services.

## File Naming Conventions

- **Python files**: `snake_case.py`
- **Templates**: `snake_case.html`, partials in `partials/` subdirectory
- **Static files**: `kebab-case.css`, `kebab-case.js`
- **Components**: `_component_name.html` (underscore prefix for partials)

---

## Code Style

### Python

- Use type hints everywhere
- Docstrings for public functions
- Black for formatting (line length 88)
- Ruff for linting
- isort for imports

### Templates

- 4-space indentation
- Keep logic minimal - compute in views
- Use template tags for complex logic

### JavaScript (Alpine.js)

- Inline for simple components
- External `x-data` for complex state
- Prefer declarative over imperative