
def base_template_context(request):
    """
    Context processor that returns the appropriate base template
    based on the 'app_mode' session variable or the request host.
    """
    host = request.get_host()
    if "blogs.iesmartinabescos" in host:
        base_template = "blogs/base.html"
    elif request.session.get("app_mode") == "incidencias":
        base_template = "incidencias/base_incidencias.html"
    elif request.session.get("app_mode") == "wifi":
        base_template = "wifi/base_wifi.html"
    else:
        base_template = "base.html"

    return {"base_template": base_template}
