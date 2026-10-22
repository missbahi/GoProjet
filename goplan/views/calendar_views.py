import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from projets.utils.navigation import crumb

from ..calendar_forms import CalendarExceptionFormSet, CalendarForm, WEEKDAYS
from ..models import GWorkCalendar
from ..services.calendar import WorkCalendarService

logger = logging.getLogger(__name__)


def _breadcrumbs(label=None):
    items = [
        crumb("Accueil", "projets:home"), crumb("Plannings", "goplan:liste_plans"),
        crumb("Calendriers", "goplan:liste_calendriers") if label else crumb("Calendriers"),
    ]
    if label:
        items.append(crumb(label))
    return items


@login_required
def liste_calendriers(request):
    calendars = GWorkCalendar.objects.annotate(
        plans_count=Count("gplan", distinct=True), 
        resources_count=Count("gresource", distinct=True),
        exceptions_count=Count("exceptions", distinct=True),
    ).order_by("-is_default", "nom", "pk")

    for calendar in calendars:
        calendar.workday_labels = [label for day, label in WEEKDAYS if day in calendar.jours_ouvres]

    # Si la requête est GET, appel du template HTML pour afficher la liste des calendriers
    ctx = {
        'calendars': calendars,
        'breadcrumb_items': _breadcrumbs(),
    }
    
    if request.headers.get('HX-Request'):
            return render(request, 'goplan/calendars/_liste_calendriers_content.html', ctx)
    
    return render(request, "goplan/calendars/liste_calendriers.html", ctx)


@login_required
@require_http_methods(["GET", "POST"])
def calendrier_form(request, calendar_id=None):
    calendar = get_object_or_404(GWorkCalendar, pk=calendar_id) if calendar_id else GWorkCalendar()
    data = request.POST if request.method == "POST" else None

    form = CalendarForm(data, instance=calendar)
    exceptions = CalendarExceptionFormSet(
        data, instance=calendar, prefix="exceptions",
    )

    if request.method == "POST":
        if form.is_valid() and exceptions.is_valid():
            try:
                candidate = form.save(commit=False)
                # Validation préalable (cohérence jours/heures)
                WorkCalendarService(candidate)
                with transaction.atomic():
                    if candidate.is_default:
                        GWorkCalendar.objects.filter(is_default=True) \
                            .exclude(pk=candidate.pk).update(is_default=False)
                    candidate.save()
                    exceptions.instance = candidate
                    exceptions.save()
            except ValidationError as error:
                form.add_error(None, error)
            except DatabaseError:
                logger.exception("Impossible d'enregistrer le calendrier %s", calendar_id)
                form.add_error(None, "Enregistrement impossible. Aucune modification n'a été sauvegardée.")
            else:
                messages.success(request, f"Calendrier « {candidate.nom} » enregistré.")
                return redirect("goplan:liste_calendriers")

    ctx = {
        "form": form,
        "exceptions": exceptions,
        "calendar": calendar,
        "breadcrumb_items": _breadcrumbs("Modifier" if calendar_id else "Nouveau calendrier"),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'goplan/calendars/_calendrier_form_content.html', ctx)
    return render(request, "goplan/calendars/calendrier_form.html", ctx)

@login_required
@require_POST
def supprimer_calendrier(request, calendar_id):
    calendar = get_object_or_404(GWorkCalendar, pk=calendar_id)
    try:
        with transaction.atomic():
            calendar = GWorkCalendar.objects.select_for_update().get(pk=calendar.pk)
            if calendar.gplan_set.exists() or calendar.gresource_set.exists():
                messages.error(request, "Ce calendrier est utilisé par un planning ou une ressource et ne peut pas être supprimé.")
            else:
                calendar.delete()
                messages.success(request, f"Calendrier « {calendar.nom} » supprimé.")
    except DatabaseError:
        logger.exception("Impossible de supprimer le calendrier %s", calendar_id)
        messages.error(request, "La suppression du calendrier a échoué.")
    return redirect("goplan:liste_calendriers")
