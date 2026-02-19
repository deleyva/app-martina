from django.conf import settings
from django.shortcuts import render
from wagtail.views import serve as wagtail_serve

def smart_home_view(request):
    """
    Acts as a traffic controller for the root URL.
    - If the current site is the default one (Main App), show the App Dashboard.
    - Otherwise (e.g. blog domain), delegate to Wagtail to serve its root page.
    """
    # Assuming SITE_ID=1 is the main "Apps" site (apps.iesmartinabescos.es)
    # This relies on CurrentSiteMiddleware populating request.site
    if request.site.id == getattr(settings, "SITE_ID", 1):
        return render(request, "pages/home.html")
    
    # If it's another specific site (like the blog), let Wagtail handle it.
    # Wagtail's serve view will look up the Site and Page matching the request.
    return wagtail_serve(request, request.path)
