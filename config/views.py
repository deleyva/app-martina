from django.conf import settings
from django.shortcuts import render
from wagtail.views import serve as wagtail_serve
from django.contrib.sites.models import Site

def smart_home_view(request):
    """
    Acts as a traffic controller for the root URL.
    - If the request host matches the Default Site domain (Apps), show the App Dashboard.
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
        return render(request, "pages/home.html")
    
    # If it's another domain (blogs.ies...), let Wagtail handle it.
    return wagtail_serve(request, request.path)
