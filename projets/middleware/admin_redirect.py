from django.shortcuts import redirect


class AdminRedirectMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Redirige si l'utilisateur est sur la page principale de l'admin après connexion
        if (request.user.is_authenticated and 
            request.path == '/admin/' and
            response.status_code == 200):
            return redirect('home')
        
        return response
