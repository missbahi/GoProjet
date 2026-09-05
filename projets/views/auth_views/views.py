from django.contrib import messages
from django.shortcuts import render
from django.urls import reverse_lazy
from django.contrib.auth import views as auth_views


class CustomLoginView(auth_views.LoginView):
    template_name = 'authentification/login.html'

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

    def form_valid(self, form):
        messages.info(self.request, 'Un email de réinitialisation a été envoyé.')
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