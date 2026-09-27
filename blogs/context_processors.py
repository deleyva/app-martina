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
    from blogs.models import AMBITOS, BlogIndexPage

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
    # El departamento en el que estás, para subrayarlo en el menú. Se saca de
    # la URL y no de `page.get_parent()`: la ruta de un departamento es
    # `/<slug>/` y la de sus artículos `/<slug>/<articulo>/`, así que el primer
    # tramo basta y no cuesta ninguna consulta.
    tramos = request.path.strip("/").split("/")
    actual = tramos[0] if tramos else ""

    # Menú en dos niveles: ámbitos arriba, departamentos del ámbito abierto
    # debajo. Un ámbito sin departamentos no aparece. El ámbito del
    # departamento actual viene abierto.
    por_ambito = {clave: [] for clave, _ in AMBITOS}
    for d in departamentos:
        por_ambito.setdefault(d.ambito or "centro", []).append(d)
    ambitos = [
        {
            "clave": clave,
            "nombre": nombre,
            "departamentos": por_ambito[clave],
            "activo": any(d.slug == actual for d in por_ambito[clave]),
        }
        for clave, nombre in AMBITOS
        if por_ambito.get(clave)
    ]
    return {
        "blog_departments": departamentos,
        "blog_departamento_actual": actual,
        "blog_ambitos": ambitos,
    }
