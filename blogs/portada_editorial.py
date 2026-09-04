"""Portada editorial del sitio de blogs — construida, completa y NUNCA servida.

Apareció al partir `cms` en la fase 25 y merece que alguien decida qué hacer con
ello, porque no es código muerto por descuido: es una portada editorial entera
—slider de destacados, tira de editoriales, secciones por departamento con barra
lateral— con sus cuatro plantillas escritas y su contexto calculado.

Por qué no se ve nunca: vivía en `HomePage.get_context()`, detrás de un
`if _is_blog_request(request)`, y `HomePage` solo existe bajo
`apps.iesmartinabescos.es`. La raíz del sitio de blogs es un `BlogIndexPage`
(id=60), no una `HomePage`. El comentario original —«cuando esta HomePage se
sirve bajo el host del blog, `self` ES la raíz del site de blogs»— describe un
montaje que la base de datos nunca ha tenido. La rama no se ha ejecutado jamás.

Se conserva aquí en vez de borrarse, y desconectada en vez de encenderse, porque
encenderla cambia la portada que ve el profesorado y esa no es mi decisión.

**Para encenderla**, en `BlogIndexPage.get_context()`:

    from blogs.portada_editorial import contexto_portada_editorial
    if is_hub:
        context.update(contexto_portada_editorial(self, request))

y que `get_template()` devuelva `blogs/portada_editorial.html` para el hub. Las
plantillas están en `blogs/templates/blogs/` con ese nombre y sus tres parciales
`_editorial_*.html`.
"""

from wagtail.models import Page

from blogs.models import ArticuloPage, BlogIndexPage


def contexto_portada_editorial(pagina, request):
    """Contexto de la portada editorial. `pagina` es la raíz del sitio de blogs.

    Devuelve el diccionario tal cual lo calculaba `HomePage`; el llamante decide
    si lo mete en el contexto o no.
    """
    contexto = {}
    root = pagina

    # Departamentos = BlogIndexPage hijos directos del root del sitio.
    # Naturalmente excluye BlogIndexPage anidados bajo MusicLibraryIndexPage.
    departments = list(
        BlogIndexPage.objects.child_of(root)
        .live()
        .specific()
        .order_by("title")
    )

    # Hero: destacados más recientes del subsite entero.
    hero_posts = list(
        ArticuloPage.objects.descendant_of(root)
        .live()
        .filter(is_featured=True)
        .select_related("featured_image")
        .order_by("-first_published_at")[:6]
    )

    # Editoriales: últimos 8 posts (excluyendo los del hero para no duplicar).
    hero_ids = [p.pk for p in hero_posts]
    editorial_posts = list(
        ArticuloPage.objects.descendant_of(root)
        .live()
        .exclude(pk__in=hero_ids)
        .select_related("featured_image")
        .order_by("-first_published_at")[:8]
    )

    # Secciones por departamento: hasta 4, ordenadas por fecha del post
    # más reciente descendente. Se excluyen departamentos sin posts.
    dated_sections = []
    undated_sections = []
    for dept in departments:
        dept_posts = list(
            ArticuloPage.objects.descendant_of(dept)
            .live()
            .select_related("featured_image")
            .order_by("-first_published_at")[:4]
        )
        if not dept_posts:
            continue
        section = {
            "department": dept,
            "main": dept_posts[0],
            "secondary": dept_posts[1:4],
        }
        latest = dept_posts[0].first_published_at
        if latest is not None:
            dated_sections.append((latest, section))
        else:
            undated_sections.append(section)

    dated_sections.sort(key=lambda pair: pair[0], reverse=True)
    ordered_sections = [s for _, s in dated_sections] + undated_sections
    department_sections = ordered_sections[:4]

    # Sidebar "NUEVO" global — 5 posts más recientes de todo el subsite.
    sidebar_recent = list(
        ArticuloPage.objects.descendant_of(root)
        .live()
        .select_related("featured_image")
        .order_by("-first_published_at")[:5]
    )

    # Batch-resolve parent department titles para los posts cuyos templates
    # mostrarán "fecha · departamento". Evita el N+1 que provocaría
    # `post.get_parent.specific.title` dentro de un loop de template
    # (sería 2 queries por post: get_parent + .specific).
    posts_needing_dept = list(hero_posts) + list(sidebar_recent)
    if posts_needing_dept:
        steplen = Page.steplen
        parent_paths = {
            p.path[:-steplen]
            for p in posts_needing_dept
            if len(p.path) > steplen
        }
        parent_titles = dict(
            Page.objects.filter(path__in=parent_paths).values_list(
                "path", "title"
            )
        )
        for p in posts_needing_dept:
            p.dept_title = parent_titles.get(p.path[:-steplen], "")

    contexto["hero_posts"] = hero_posts
    contexto["editorial_posts"] = editorial_posts
    contexto["department_sections"] = department_sections
    contexto["sidebar_recent"] = sidebar_recent
    return contexto
