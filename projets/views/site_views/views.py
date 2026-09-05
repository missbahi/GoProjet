import json
from datetime import date, datetime

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Avg, Sum
from django.shortcuts import redirect, render
from django.utils.timezone import timedelta
from django.views.decorators.http import require_GET

from projets.decorators import projets_accessibles
from projets.models import Notification, Tache


def landing(request):
    if request.user.is_authenticated:
        return redirect('projets:liste_projets')
    return render(request, 'projets/apropos.html')


@login_required
def home(request):
    today = date.today()
    profile = request.user.profile
    projets_utilisateur = projets_accessibles(request.user)
    projets_recents = projets_utilisateur.order_by('-date_creation')[:5]
    projets_pour_graphiques = projets_utilisateur.order_by('-date_creation')[:10]
    projets_en_retard = projets_utilisateur.filter(en_retard=True).order_by('-date_debut')[:5]
    nouveaux_ao = projets_utilisateur.filter(a_traiter=True).order_by('-date_creation')[:5]
    receptions_validees = projets_utilisateur.filter(reception_validee=True).order_by('-date_reception')[:5]

    nb_projets_en_cours = projets_utilisateur.filter(statut='COURS').count()
    nb_projets_en_retard = projets_utilisateur.filter(en_retard=True).count()
    avancement_moyen = projets_utilisateur.filter(statut='COURS').aggregate(moy=Avg('avancement'))['moy'] or 0
    avancement_moyen = float(avancement_moyen)
    nb_appels_offres = projets_utilisateur.filter(statut='AO').count()
    nb_a_traiter = projets_utilisateur.filter(a_traiter=True).count()
    nb_receptions_validees = projets_utilisateur.filter(reception_validee=True).count()
    nb_receptions_en_retard = projets_utilisateur.filter(reception_validee=True, en_retard=True).count()
    annee_courante = date.today().year
    ca_total = projets_utilisateur.filter(date_debut__year=annee_courante).aggregate(total=Sum('montant'))['total'] or 0
    notifications = Notification.objects.filter(utilisateur=request.user, lue=False).order_by('-date_creation')[:5]
    nb_notifications = Notification.objects.filter(utilisateur=request.user, lue=False).count()

    resume_cartes = [
        {'titre': 'Projets en cours', 'valeur': nb_projets_en_cours, 'couleur': 'blue', 'icône': 'fa-hard-hat', 'sous_titre': 'Avancement moyen', 'sous_valeur': f'{avancement_moyen:.0f} %', 'progress': round(avancement_moyen)},
        {'titre': "Appels d'offres", 'valeur': nb_appels_offres, 'couleur': 'cyan', 'icône': 'fa-file-signature', 'sous_titre': 'À traiter', 'sous_valeur': nb_a_traiter, 'progress': round((nb_a_traiter / nb_appels_offres) * 100) if nb_appels_offres else 0},
        {'titre': 'Réceptions validées', 'valeur': nb_receptions_validees, 'couleur': 'purple', 'icône': 'fa-check-circle', 'sous_titre': 'En retard', 'sous_valeur': nb_receptions_en_retard, 'progress': round((nb_receptions_en_retard / nb_receptions_validees) * 100) if nb_receptions_validees else 0},
        {'titre': "Chiffre d'affaires", 'valeur': f'{round(ca_total / 1_000_000, 1)}M MAD', 'couleur': 'orange', 'icône': 'fa-coins', 'sous_titre': 'Cette année', 'sous_valeur': f'{nb_receptions_validees} réceptions', 'progress': min(100, nb_receptions_validees * 10)},
    ]
    echeances = Tache.objects.filter(date_fin__gte=today).order_by('date_fin')[:3]
    chart_data = {
        'projets': [],
        'categories': ['Mensuel', 'Trimestriel', 'Annuel'],
        'stats': {
            'avancement_moyen': round(avancement_moyen, 0),
            'nb_projets': projets_utilisateur.count(),
            'nb_en_retard': nb_projets_en_retard,
        },
    }

    for projet in projets_pour_graphiques:
        avancement = float(projet.avancement) or 0
        if avancement < 20:
            couleur, statut_color = '#ef4444', 'Critique'
        elif avancement < 40:
            couleur, statut_color = '#f97316', 'En retard'
        elif avancement < 60:
            couleur, statut_color = '#eab308', 'En cours'
        elif avancement < 80:
            couleur, statut_color = '#22c55e', 'Bien avancé'
        else:
            couleur, statut_color = '#16a34a', 'Presque terminé'
        date_debut = projet.date_debut or date.today()
        date_fin_prevue = date_debut + timedelta(days=projet.delai or 0)
        chart_data['projets'].append({
            'id': projet.id,
            'nom': projet.nom,
            'nom_court': projet.nom[:15] + '...' if len(projet.nom) > 15 else projet.nom,
            'avancement': round(avancement),
            'montant': float(projet.montant or 0),
            'couleur': couleur,
            'statut_color': statut_color,
            'statut': projet.statut,
            'en_retard': projet.en_retard,
            'date_creation': projet.date_creation.strftime('%Y-%m-%d') if projet.date_creation else None,
            'date_fin_prevue': date_fin_prevue.strftime('%Y-%m-%d') if date_fin_prevue else None,
        })

    now = datetime.now()
    projets_mensuels = projets_utilisateur.filter(date_creation__gte=now - timedelta(days=30))
    chart_data['mensuel'] = {'labels': ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4'], 'avancements': [65, 72, 68, 75]}
    chart_data['trimestriel'] = {'labels': ['Mois 1', 'Mois 2', 'Mois 3'], 'avancements': [60, 68, 72]}
    chart_data['annuel'] = {'labels': ['Q1', 'Q2', 'Q3', 'Q4'], 'avancements': [55, 65, 70, 68]}

    return render(request, 'projets/home.html', {
        'projets_recents': projets_recents,
        'projets_en_retard': projets_en_retard,
        'nouveaux_ao': nouveaux_ao,
        'receptions_validees': receptions_validees,
        'resume_cartes': resume_cartes,
        'notifications': notifications,
        'nb_notifications': nb_notifications,
        'profile': profile,
        'echeances': echeances,
        'chart_data_json': json.dumps(chart_data, cls=DjangoJSONEncoder),
        'projets_noms': json.dumps([projet.nom for projet in projets_utilisateur]),
        'projets_noms_recents': json.dumps([projet.nom for projet in projets_recents]),
        'projets_avancements': json.dumps([round(projet.avancement) if projet.avancement is not None else 0 for projet in projets_utilisateur]),
        'avancement_projets_recents': json.dumps([round(projet.avancement) if projet.avancement is not None else 0 for projet in projets_recents]),
    })


def apropos(request):
    return render(request, 'projets/apropos.html')


@require_GET
def offline_view(request):
    return render(request, 'projets/offline.html')


def permission_denied(request, exception=None):
    return render(request, 'errors/access_restricted.html', status=403)


def page_not_found(request, exception=None):
    return render(request, 'errors/access_restricted.html', {
        'page_not_found': True,
    }, status=404)

