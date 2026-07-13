# Esta documentación

Construida con [MkDocs](https://www.mkdocs.org/) y el tema [Material](https://squidfunk.github.io/mkdocs-material/), publicada automáticamente en **GitHub Pages**.

## Estructura

- `mkdocs.yml` en la raíz del repo (configuración y navegación).
- `documentacion/` contiene las páginas Markdown (en español).
- `.github/workflows/docs.yml` construye y despliega en cada push a `main` que toque la documentación.

## Editar en local

```bash
pip install mkdocs-material
mkdocs serve        # http://127.0.0.1:8000 con recarga en vivo
mkdocs build --strict
```

## Publicación

El workflow de GitHub Actions usa el flujo oficial de Pages (`actions/deploy-pages`): no hay rama `gh-pages`, el sitio se sirve desde el artefacto del build.

!!! important "Activar Pages la primera vez"
    En GitHub: **Settings → Pages → Source → GitHub Actions**. Tras el primer push a `main`, el sitio queda en `https://deleyva.github.io/app-martina/`.

Los diagramas usan Mermaid mediante `pymdownx.superfences`; se escriben en bloques ```` ```mermaid ````.
