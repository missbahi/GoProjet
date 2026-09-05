import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from projets.decorators import projets_accessibles
from projets.forms import TacheForm
from projets.models import Projet, Tache

logger = logging.getLogger(__name__)


class ListeTachesView(LoginRequiredMixin, ListView):
    model = Tache
    template_name = 'projets/taches/liste_taches.html'
    context_object_name = 'taches'

    def get_queryset(self):
        user = self.request.user
        queryset = Tache.objects.select_related('projet', 'responsable')

        if not user.is_superuser:
            queryset = queryset.filter(projet__in=projets_accessibles(user))

        terminee_param = self.request.GET.get('terminee', '').strip().lower()
        terminee_val = None
        if terminee_param in ['true', '1']:
            terminee_val = True
        elif terminee_param in ['false', '0']:
            terminee_val = False

        filters = {
            'responsable_id': self.request.GET.get('responsable') or None,
            'terminee': terminee_val,
            'priorite': self.request.GET.get('priorite') or None,
        }

        return queryset.filter(**{k: v for k, v in filters.items() if v is not None})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        if user.is_superuser:
            context['responsables'] = User.objects.filter(tache__isnull=False).distinct()
        else:
            context['responsables'] = User.objects.filter(
                projets__in=projets_accessibles(user)
            ).distinct()

        return context


@login_required
def get_form_data(request):
    user = request.user
    if user.is_superuser:
        projets = Projet.objects.all().values('id', 'nom')
        responsables = User.objects.all().values('id', 'username')
    else:
        projets = projets_accessibles(user).values('id', 'nom')
        responsables = User.objects.filter(
            projets__in=projets_accessibles(user)
        ).distinct().values('id', 'username')

    priorites = [
        {'value': value, 'label': label}
        for value, label in Tache.PRIORITE
    ]

    return JsonResponse({
        'projets': list(projets),
        'responsables': list(responsables),
        'priorites': priorites,
    })


class CreerTacheView(LoginRequiredMixin, CreateView):
    model = Tache
    form_class = TacheForm
    success_url = reverse_lazy('projets:liste_taches')

    def post(self, request, *args, **kwargs):
        logger.info(
            f"Création tâche - User: {request.user} - Données: {request.POST.dict()}"
        )
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        try:
            self.object = form.save()

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'tache_id': self.object.id,
                    'message': 'Tâche créée avec succès',
                    'data': {
                        'titre': self.object.titre,
                        'projet': self.object.projet.nom if self.object.projet else None,
                        'statut': 'Terminée' if self.object.terminee else 'En cours',
                    },
                })

            return super().form_valid(form)

        except Exception as e:
            logger.error(f"Erreur création tâche: {str(e)}")
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Erreur serveur lors de la création',
                }, status=500)
            raise

    def form_invalid(self, form):
        logger.warning(
            f"Formulaire invalide - Erreurs: {form.errors.as_json()}"
        )

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data(),
                'message': 'Veuillez corriger les erreurs ci-dessous',
                'error_fields': list(form.errors.keys()),
            }, status=400)

        return super().form_invalid(form)


class ModifierTacheView(LoginRequiredMixin, UpdateView):
    model = Tache
    form_class = TacheForm
    template_name = 'projets/taches/modifier_tache.html'
    success_url = reverse_lazy('projets:liste_taches')

    def get_queryset(self):
        qs = Tache.objects.select_related('projet', 'responsable')
        if not self.request.user.is_superuser:
            qs = qs.filter(projet__in=projets_accessibles(self.request.user))
        return qs

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        logger.info(
            f"Modification tâche ID {self.object.id} - User: {request.user} - Données: {request.POST.dict()}"
        )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            self.object = form.save()

            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'tache_id': self.object.id,
                    'message': 'Tâche mise à jour avec succès',
                    'changes': form.changed_data,
                    'new_data': {
                        'statut': 'Terminée' if self.object.terminee else 'En cours',
                        'avancement': f"{self.object.avancement}%",
                    },
                })

            return super().form_valid(form)

        except Exception as e:
            logger.error(f"Erreur modification tâche: {str(e)}")
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Erreur serveur lors de la mise à jour',
                }, status=500)
            raise

    def form_invalid(self, form):
        logger.warning(
            f"Formulaire modification invalide - ID: {self.object.id} - Erreurs: {form.errors.as_json()}"
        )

        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data(),
                'message': 'Veuillez corriger les erreurs ci-dessous',
                'error_fields': list(form.errors.keys()),
            }, status=400)

        return super().form_invalid(form)


class DetailTacheView(LoginRequiredMixin, DetailView):
    model = Tache
    template_name = 'projets/taches/tache_details.html'
    context_object_name = 'tache'

    def get_queryset(self):
        qs = Tache.objects.select_related('projet', 'responsable')
        if not self.request.user.is_superuser:
            qs = qs.filter(projet__in=projets_accessibles(self.request.user))
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        tache = self.object
        context['priorite_display'] = tache.get_priorite_display()
        context['est_en_retard'] = (
            tache.date_fin and tache.date_fin < timezone.now().date() and not tache.terminee
        )
        return context

    def render_to_json_response(self):
        tache = self.object
        return JsonResponse({
            'success': True,
            'data': {
                'id': tache.id,
                'titre': tache.titre,
                'priorite': tache.priorite,
                'terminee': tache.terminee,
                'avancement': tache.avancement,
                'description': tache.description,
                'date_debut': tache.date_debut.isoformat() if tache.date_debut else None,
                'date_fin': tache.date_fin.isoformat() if tache.date_fin else None,
                'projet': {
                    'id': tache.projet.id if tache.projet else None,
                    'nom': tache.projet.nom if tache.projet else None,
                },
                'responsable': {
                    'id': tache.responsable.id if tache.responsable else None,
                    'nom_complet': tache.responsable.get_full_name() if tache.responsable else None,
                    'username': tache.responsable.username if tache.responsable else None,
                },
            },
        })

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                return self.render_to_json_response()
            except Exception as e:
                logger.error(f"Erreur détail tâche {self.object.id}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': "Erreur lors du chargement des données",
                }, status=500)

        return super().get(request, *args, **kwargs)


class SupprimerTacheView(LoginRequiredMixin, DeleteView):
    model = Tache
    success_url = reverse_lazy('projets:liste_taches')

    def get_queryset(self):
        qs = Tache.objects.all()
        if not self.request.user.is_superuser:
            qs = qs.filter(projet__in=projets_accessibles(self.request.user))
        return qs

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()

        try:
            self.object.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Tâche supprimée avec succès',
                })
            return super().delete(request, *args, **kwargs)

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': str(e),
                }, status=400)
            raise
