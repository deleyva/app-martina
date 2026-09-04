"""El menú de departamentos, disponible en todas las páginas del sitio de blogs.

Vivía en `cms/context_processors.py` y decidía con `_is_blog_request(request)`,
que comparaba el `Host` con una cadena. Al partir la app ese helper desapareció y
aquí ya no hace falta: los departamentos son `blogs.BlogIndexPage`, un modelo que
solo existe en este sitio. Si no hay ninguno colgando de la raíz, el sitio no es
el de blogs y devolvemos `{}`.

Se pregunta por el modelo, no por el hostname. Es más barato de mantener: el día
que el dominio cambie no hay que acordarse de venir aquí.
"""

from wagtail.models import Site


def blog_navigation(request):
    """Inyecta `blog_departments` cuando se sirve el sitio de blogs; `{}` si no."""
    # Import local: `blogs.models` carga Wagtail, que puede pedir settings antes
    # de que Django esté listo.
    from blogs.models import BlogIndexPage

    site = Site.find_for_request(request)
    if site is None:
        return {}

    raiz = site.root_page
    if not isinstance(raiz.specific_deferred, BlogIndexPage):
        return {}

    departamentos = list(
        BlogIndexPage.objects.child_of(raiz).live().specific().order_by("title")
    )
    if not departamentos:
        return {}
    return {"blog_departments": departamentos}
