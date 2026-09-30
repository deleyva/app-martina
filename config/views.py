from django.conf import settings
from django.http import HttpResponseRedirect
from wagtail.views import serve as wagtail_serve
from django.contrib.sites.models import Site

def smart_home_view(request):
    """
    Acts as a traffic controller for the root URL.
    - If the request host matches the Default Site domain (Apps), redirect to the music library index.
    - Otherwise (e.g. blog domain), delegate to Wagtail to serve its root page.
    """
    try:
        # Get the 'Apps' site (ID 1 by default)
        default_site = Site.objects.get(pk=getattr(settings, "SITE_ID", 1))
        default_domain = default_site.domain
    except Site.DoesNotExist:
        # Emergency fallback if Site 1 is deleted
        default_domain = "apps.iesmartinabescos.es"

    host = request.get_host()
    
    # Check if current host matches the main app domain
    # loose check "in" allows for port numbers in dev (localhost:8000)
    if default_domain in host:
        # La raíz de apps. no tenía contenido (pages/home.html era solo el
        # `extends`): quien entra por el dominio pelado va al índice de recursos.
        # 302 y no 301 a propósito: un 301 lo cachea el navegador y, el día que
        # la raíz tenga portada propia, habría gente atrapada en el salto.
        # El querystring (`?lang=en`) viaja con la redirección.
        destino = "/indice-de-recursos-musicales/"
        if request.META.get("QUERY_STRING"):
            destino += "?" + request.META["QUERY_STRING"]
        return HttpResponseRedirect(destino)
    
    # If it's another domain (blogs.ies...), let Wagtail handle it.
    return wagtail_serve(request, request.path)
