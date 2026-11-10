from decimal import Decimal
import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.formats import number_format
from django.views.decorators.http import require_GET

from projets.decorators import projets_accessibles
from projets.models import Notification, Tache
from projets.services.home_indicators import indicateurs_home


def landing(request):
    if request.user.is_authenticated:
        return redirect('projets:liste_projets')
    return render(request, 'projets/landing/apropos.html')


@login_required
def home(request):
    today = timezone.localdate()
    profile = request.user.profile
    projets_utilisateur = projets_accessibles(request.user)
    projets = list(projets_utilisateur.select_related('entreprise', 'dossier').order_by('-date_creation', '-pk'))
    indicateurs = indicateurs_home(projets, today)
    projets_recents = projets[:5]
    projets_pour_graphiques = projets[:10]
    projets_en_retard = [p for p in projets if p.home_en_retard]
    en_cours = [p for p in projets if p.statut == 'COURS']
    avances = [p.home_avancement for p in en_cours if p.home_avancement is not None]
    avancement_moyen = sum(avances, Decimal('0')) / len(avances) if avances else None
    notifications = Notification.objects.filter(utilisateur=request.user, lue=False).order_by('-date_creation')[:5]
    nb_notifications = Notification.objects.filter(utilisateur=request.user, lue=False).count()

    resume_cartes = [
        {'titre': 'Projets en cours', 'valeur': len(en_cours), 'couleur': 'blue', 'icône': 'fa-hard-hat',
         'sous_titre': f'Avancement moyen ({len(avances)}/{len(en_cours)} renseignés)',
         'sous_valeur': f'{number_format(avancement_moyen, 1)} %' if avancement_moyen is not None else 'Non disponible',
         'progress': max(0, min(100, round(avancement_moyen))) if avancement_moyen is not None else None},
        {'titre': f"CA de production {today.year} HT", 'valeur': number_format(indicateurs['ca_annuel'], 2, force_grouping=True),
         'icône': 'fa-coins', 'sous_titre': 'Dont brouillons',
         'sous_valeur': number_format(indicateurs['ca_annuel_brouillon'], 2, force_grouping=True), 'progress': None},
        {'titre': 'Production CA cumulée HT', 'valeur': number_format(indicateurs['production_ca'], 2, force_grouping=True),
         'icône': 'fa-chart-line', 'sous_titre': f"{indicateurs['nb_ca']} projets suivis",
         'sous_valeur': f"{indicateurs['nb_ca_brouillons']} CA en brouillon", 'progress': None},
        {'titre': 'Attachements validés cumulés HT',
         'valeur': number_format(indicateurs['attachements_valides'], 2, force_grouping=True),
         'icône': 'fa-file-signature', 'sous_titre': 'Dernier cumul validé par projet',
         'sous_valeur': f"{indicateurs['nb_attachements']} projets", 'progress': None},
    ]
    echeances = Tache.objects.filter(
        projet__in=projets_utilisateur, date_fin__gte=today, terminee=False,
    ).order_by('date_fin', 'pk')[:3]
    chart_data = {
        'projets': [],
        'stats': {
            'avancement_moyen': float(avancement_moyen) if avancement_moyen is not None else None,
            'nb_projets': len(projets),
            'nb_en_retard': len(projets_en_retard),
        },
    }

    for projet in projets_pour_graphiques:
        avancement = float(projet.home_avancement) if projet.home_avancement is not None else None
        if avancement is None:
            couleur, statut_color = '#9ca3af', 'Non renseigné'
        elif avancement < 20:
            couleur, statut_color = '#f97316', 'Début de production'
        elif avancement < 40:
            couleur, statut_color = '#eab308', 'En progression'
        elif avancement < 60:
            couleur, statut_color = '#eab308', 'En cours'
        elif avancement < 80:
            couleur, statut_color = '#22c55e', 'Bien avancé'
        else:
            couleur, statut_color = '#16a34a', 'Presque terminé'
        date_fin_prevue = projet.home_echeance
        chart_data['projets'].append({
            'id': projet.id,
            'nom': projet.nom,
            'nom_court': projet.nom[:15] + '...' if len(projet.nom) > 15 else projet.nom,
            'avancement': round(avancement, 1) if avancement is not None else None,
            'source': projet.home_source, 'provisoire': projet.home_provisoire,
            'montant': float(projet.home_marche_ht),
            'couleur': couleur,
            'statut_color': statut_color,
            'statut': projet.statut,
            'en_retard': projet.home_en_retard,
            'date_creation': projet.date_creation.strftime('%Y-%m-%d') if projet.date_creation else None,
            'date_fin_prevue': date_fin_prevue.strftime('%Y-%m-%d') if date_fin_prevue else None,
        })

    context = {
        'projets_recents': projets_recents,
        'projets_en_retard': projets_en_retard[:5],
        'resume_cartes': resume_cartes,
        'notifications': notifications,
        'nb_notifications': nb_notifications,
        'profile': profile,
        'echeances': echeances,
        'chart_data_json': json.dumps(chart_data, cls=DjangoJSONEncoder),
        'chart_data': chart_data,
        'indicateurs_home': indicateurs, 'date_indicateurs': today,
        'nb_projets_en_retard': len(projets_en_retard),
        'nb_echeances_a_verifier': sum(bool(p.home_echeance_erreur) for p in projets),
        'projets_noms': json.dumps([projet.nom for projet in projets]),
        'projets_noms_recents': json.dumps([projet.nom for projet in projets_recents]),
        'projets_avancements': json.dumps([float(p.home_avancement) if p.home_avancement is not None else None for p in projets]),
        'avancement_projets_recents': json.dumps([float(p.home_avancement) if p.home_avancement is not None else None for p in projets_recents]),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'projets/home/_home_content.html', context)

    return render(request, 'projets/home/home.html', context)


def apropos(request):
    return render(request, 'projets/landing/apropos.html')


@require_GET
def offline_view(request):
    return render(request, 'projets/landing/offline.html')


def permission_denied(request, exception=None):
    return render(request, 'errors/access_restricted.html', status=403)


def page_not_found(request, exception=None):
    return render(request, 'errors/access_restricted.html', {
        'page_not_found': True,
    }, status=404)
