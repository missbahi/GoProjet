from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings

class AuthRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # URLs autorisées sans authentification
        public_urls = [
            reverse('admin:login'),
            '/admin/logout/',
            '/static/',
            '/media/',
        ]
        
        # Vérifier si l'URL actuelle nécessite une authentification
        if not request.user.is_authenticated and not any(request.path.startswith(url) for url in public_urls):
            return redirect(settings.LOGIN_URL)
        
        response = self.get_response(request)
        return response