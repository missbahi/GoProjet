from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F

from projets.models import OrdreService, Projet, TypeOrdreService


def normaliser_sequence(projet):
    """Renumérote les OS du projet de 1 à n en conservant l'ordre actuel (supprime trous et doublons)."""
    with transaction.atomic():
        Projet.objects.select_for_update().get(pk=projet.pk)
        ordres = OrdreService.objects.filter(projet=projet).order_by(
            'ordre_sequence', 'date_publication', 'pk',
        )
        for numero, ordre in enumerate(ordres, start=1):
            if ordre.ordre_sequence != numero:
                OrdreService.objects.filter(pk=ordre.pk).update(ordre_sequence=numero)


def _inserer_apres_date(projet, type_os, date_effet, **champs):
    """Insère l'OS juste après le dernier OS (non annulé) daté au plus tard à date_effet
    et décale les suivants, sans toucher aux numéros précédents."""
    precedents = OrdreService.objects.filter(
        projet=projet, date_effet__isnull=False, date_effet__lte=date_effet,
    ).exclude(statut='ANNULE')
    position = max(precedents.values_list('ordre_sequence', flat=True), default=0)
    OrdreService.objects.filter(projet=projet, ordre_sequence__gt=position).update(
        ordre_sequence=F('ordre_sequence') + 1,
    )
    return OrdreService.objects.create(
        projet=projet, type_os=type_os, date_effet=date_effet, statut='NOTIFIE',
        ordre_sequence=position + 1, **champs,
    )


MODE_ARRET_REPRISE = 'ARRET_REPRISE'  # nouvelle période d'arrêt pendant les travaux
MODE_REPRISE_ARRET = 'REPRISE_ARRET'  # reprise puis nouvel arrêt à l'intérieur d'un arrêt existant


def inserer_sequence_arret_reprise(
    projet, *, date_arret, date_reprise, reference_arret, reference_reprise,
    date_publication, description='', mode=MODE_ARRET_REPRISE,
):
    """Insère atomiquement une paire OSA + OSR notifiée au bon endroit de la séquence.

    ARRET_REPRISE : arrêt < reprise, posés pendant une période de travaux.
    REPRISE_ARRET : reprise < arrêt, posés à l'intérieur d'une période d'arrêt (scinde l'arrêt).
    """
    with transaction.atomic():
        projet = Projet.objects.select_for_update().get(pk=projet.pk)
        erreurs = []

        osc = projet.ordres_service.filter(
            type_os__code='OSC', statut='NOTIFIE', date_effet__isnull=False,
        ).order_by('ordre_sequence').first()
        if not osc:
            raise ValidationError("Un OS de commencement notifié est requis avant d'insérer un arrêt.")
        if date_arret < osc.date_effet or date_reprise < osc.date_effet:
            erreurs.append("Les dates ne peuvent précéder le commencement.")
        if mode == MODE_REPRISE_ARRET:
            if date_arret <= date_reprise:
                erreurs.append("Dans une insertion « reprise puis arrêt », l'arrêt doit être postérieur à la reprise.")
        elif date_reprise <= date_arret:
            erreurs.append("La date de reprise doit être postérieure à la date d'arrêt.")
        if reference_arret == reference_reprise:
            erreurs.append("Les références de l'arrêt et de la reprise doivent être différentes.")
        existantes = set(projet.ordres_service.filter(
            reference__in=[reference_arret, reference_reprise],
        ).values_list('reference', flat=True))
        if existantes:
            erreurs.append(f"Référence déjà utilisée : {', '.join(sorted(existantes))}.")

        evenements = list(projet.ordres_service.filter(
            type_os__code__in=['OSA', 'OSR'], statut='NOTIFIE',
        ).select_related('type_os'))
        if any(e.date_effet is None for e in evenements):
            erreurs.append("Un OS d'arrêt/reprise notifié sans date d'effet empêche l'insertion.")
        if any(e.date_effet in (date_arret, date_reprise) for e in evenements):
            erreurs.append("Une date d'effet identique à celle d'un arrêt/reprise existant est ambiguë.")
        if not erreurs:
            chronologie = sorted(
                [(e.date_effet, e.type_os.code, e.reference) for e in evenements]
                + [(date_arret, 'OSA', reference_arret), (date_reprise, 'OSR', reference_reprise)]
            )
            attendu = 'OSA'
            for _, code, reference in chronologie:
                if code != attendu:
                    erreurs.append(
                        "La paire n'est pas compatible avec la chronologie existante "
                        + ("(une reprise suivie d'un arrêt doit se situer à l'intérieur d'une période d'arrêt)"
                           if mode == MODE_REPRISE_ARRET else
                           "(un arrêt suivi d'une reprise doit se situer pendant une période de travaux)")
                        + f" : alternance rompue à {reference}."
                    )
                    break
                attendu = 'OSR' if code == 'OSA' else 'OSA'

        debut_fenetre, fin_fenetre = sorted((date_arret, date_reprise))
        chevauchement = projet.attachements.exclude(statut='BROUILLON').filter(
            date_debut_periode__lt=fin_fenetre, date_fin_periode__gte=debut_fenetre,
        )
        if chevauchement.exists():
            erreurs.append(
                "Un attachement non brouillon couvre déjà la période comprise entre les deux dates ; "
                "corrigez ou repassez cet attachement en brouillon avant l'insertion."
            )
        if erreurs:
            raise ValidationError(erreurs)

        type_osa = TypeOrdreService.objects.get(code='OSA')
        type_osr = TypeOrdreService.objects.get(code='OSR')
        texte = description.strip()
        a_creer = [
            (date_arret, type_osa, reference_arret, "OS d'arrêt", texte or "Arrêt des travaux"),
            (date_reprise, type_osr, reference_reprise, "OS de reprise", texte or "Reprise des travaux"),
        ]
        a_creer.sort(key=lambda element: element[0])
        crees = [
            _inserer_apres_date(
                projet, type_os, date_effet, reference=reference, titre=titre,
                description=desc, date_publication=date_publication,
            )
            for date_effet, type_os, reference, titre, desc in a_creer
        ]
        for ordre in crees:
            ordre.full_clean()
        normaliser_sequence(projet)
        projet.update_status_flags(force_save=False)
        Projet.objects.filter(pk=projet.pk).update(en_retard=projet.en_retard)
        osa = next(o for o in crees if o.type_os.code == 'OSA')
        osr = next(o for o in crees if o.type_os.code == 'OSR')
        return osa, osr
