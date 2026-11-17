from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.contrib.auth import views as auth_views
from projets.decorators import est_observateur


class CustomLoginView(auth_views.LoginView):
    template_name = 'authentification/login.html'

    def get_success_url(self):
        if est_observateur(self.request.user):
            return reverse('projets:home')
        return super().get_success_url()

    def form_valid(self, form):
        messages.success(self.request, 'Connexion réussie !')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Identifiant ou mot de passe incorrect.')
        return super().form_invalid(form)


class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'authentification/password_reset_form.html'
    email_template_name = 'authentification/password_reset_email.html'
    subject_template_name = 'authentification/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    MAX_DEMANDES = 5
    FENETRE = 3600

    def _limite_atteinte(self, email):
        ip = self.request.META.get('REMOTE_ADDR', '')
        for cle in (f'pwreset:ip:{ip}', f'pwreset:mail:{email.lower()}'):
            cache.add(cle, 0, self.FENETRE)
            try:
                if cache.incr(cle) > self.MAX_DEMANDES:
                    return True
            except ValueError:
                cache.set(cle, 1, self.FENETRE)
        return False

    def form_valid(self, form):
        # Réponse identique que le compte existe ou non (pas d'énumération) ;
        # au-delà du plafond, l'e-mail n'est simplement pas envoyé.
        if self._limite_atteinte(form.cleaned_data['email']):
            return redirect(self.get_success_url())
        return super().form_valid(form)


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'authentification/password_reset_done.html'


class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'authentification/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

    def form_valid(self, form):
        messages.success(self.request, 'Votre mot de passe a été modifié avec succès !')
        return super().form_valid(form)


class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'authentification/password_reset_complete.html'


def access_denied(request):
    return render(request, 'authentification/access_denied.html', status=403)