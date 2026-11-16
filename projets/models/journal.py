from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db import models
from django.dispatch import receiver
from django.utils import timezone


class JournalAcces(models.Model):
    EVENT_CHOICES = [
        ('ACCES', 'Accès'),
        ('LOGIN', 'Connexion'),
        ('LOGOUT', 'Déconnexion'),
        ('ECHEC', 'Échec de connexion'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='journal_acces',
    )
    username = models.CharField(max_length=150, blank=True)
    date = models.DateTimeField(default=timezone.now, db_index=True)
    event = models.CharField(max_length=10, choices=EVENT_CHOICES, default='ACCES')
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    method = models.CharField(max_length=10, blank=True)
    path = models.CharField(max_length=500, blank=True)
    route = models.CharField(max_length=150, blank=True)
    module = models.CharField(max_length=40, blank=True)
    projet_id = models.PositiveIntegerField(null=True, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-date']
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f"{self.username} {self.event} {self.date:%Y-%m-%d %H:%M}"


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR')) or None


def _enregistrer_evenement(request, event, user, username):
    JournalAcces.objects.create(
        user=user, username=username[:150], event=event,
        ip=client_ip(request) if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT', '') if request else '')[:255],
    )


@receiver(user_logged_in)
def _journaliser_connexion(sender, request, user, **kwargs):
    _enregistrer_evenement(request, 'LOGIN', user, user.get_username())


@receiver(user_logged_out)
def _journaliser_deconnexion(sender, request, user, **kwargs):
    if user is not None:
        _enregistrer_evenement(request, 'LOGOUT', user, user.get_username())


@receiver(user_login_failed)
def _journaliser_echec(sender, credentials, request=None, **kwargs):
    _enregistrer_evenement(request, 'ECHEC', None, str(credentials.get('username', '')))
