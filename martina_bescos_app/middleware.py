
class AppModeMiddleware:
    """
    Middleware to determine the application mode (Main App vs Incidencias)
    based on the URL, to serve the appropriate base template in shared views
    like auth and user profiles.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Determine mode based on URL
        path = request.path
        
        if path.startswith('/incidencias/'):
            request.session['app_mode'] = 'incidencias'
        elif path.startswith('/accounts/') or path.startswith('/users/') or path.startswith('/admin/'):
            # Keep existing mode for auth, user profiles, and admin
            pass
        elif path.startswith('/static/') or path.startswith('/media/'):
            # Ignore static and media files
            pass
        else:
            # Default to main app for any other URL (home, other apps)
            request.session['app_mode'] = 'main'

        response = self.get_response(request)
        return response
