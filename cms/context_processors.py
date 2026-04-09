"""Context processors para el subsite de blogs.

El menú de departamentos aparece en TODAS las páginas del subsite
`blogs.iesmartinabescos.es`, por lo que necesita inyectarse vía
context processor — no solo desde `HomePage.get_context`.
"""

from wagtail.models import Site


def blog_navigation(request):
    """Inyecta `blog_departments` en el contexto cuando se sirve el subsite de blogs.

    Devuelve `{}` en el resto de hosts para no afectar al resto del sitio.
    """
    # Import local para evitar circular imports (cms.models importa de Wagtail
    # que a su vez puede cargar settings antes de que Django esté listo).
    from cms.models import BlogIndexPage, _is_blog_request

    if not _is_blog_request(request):
        return {}

    # Resolver la raíz del subsite de blogs. En producción
    # `Site.find_for_request` devuelve el site correcto (registrado como
    # `blogs.iesmartinabescos.es` en el admin de Wagtail). En local dev, o
    # cuando ese site no está registrado, puede caer al default; en ese caso
    # buscamos un Site no-default cuyo hostname contenga "blog".
    site = Site.find_for_request(request)
    if site and not site.is_default_site:
        root = site.root_page
    else:
        blog_site = (
            Site.objects.filter(hostname__icontains="blog")
            .exclude(is_default_site=True)
            .order_by("hostname")
            .first()
        )
        if not blog_site:
            return {}
        root = blog_site.root_page

    # Departamentos = BlogIndexPage que son hijos DIRECTOS del root del sitio.
    # Esto excluye automáticamente los BlogIndexPage que están anidados bajo
    # MusicLibraryIndexPage (que actúan como "libros" de la biblioteca musical).
    departments = list(
        BlogIndexPage.objects.child_of(root)
        .live()
        .specific()
        .order_by("title")
    )

    return {"blog_departments": departments}
