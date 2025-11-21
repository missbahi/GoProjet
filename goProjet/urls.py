"""
URL configuration for goProjet project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from projets import views as projets_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('projets.urls')),
    path('home/', projets_views.home, name='home'),
    
        # URLs d'authentification personnalisées
    path('accounts/login/', projets_views.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password_reset/', projets_views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('accounts/password_reset/done/', projets_views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', projets_views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/reset/done/', projets_views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('accounts/access_denied/', projets_views.access_denied, name='access_denied'),
    
]
from django.conf.urls.static import static
from django.conf import settings
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
