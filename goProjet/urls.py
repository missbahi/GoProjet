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
from projets.views.auth_views import views as auth_views_custom
from projets.views.site_views import views as site_views

handler403 = 'projets.views.site_views.views.permission_denied'
handler404 = 'projets.views.site_views.views.page_not_found'

urlpatterns = [
    path('admin/', admin.site.urls),
    # URLs PWA 
    path('', include('goProjet.pwa.urls')),
    # URLs de l'application projets
    path('', include('projets.urls')),
    
    path('home/', site_views.home, name='home'),
    
    # URLs d'authentification personnalisées
    path('accounts/login/', auth_views_custom.CustomLoginView.as_view(), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/password_reset/', auth_views_custom.CustomPasswordResetView.as_view(), name='password_reset'),
    path('accounts/password_reset/done/', auth_views_custom.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth_views_custom.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/reset/done/', auth_views_custom.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('accounts/access_denied/', auth_views_custom.access_denied, name='access_denied'),
    
]
from django.conf.urls.static import static
from django.conf import settings
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
