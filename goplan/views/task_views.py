import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projets.utils.navigation import crumb

from ..forms import GTaskInlineFormSet
from ..models import GPlan, GTask, GTaskDependency
from ..services.dependencies import recalculate_dependencies
from ..services.wbs import recalculate_wbs
from .gantt_views import _gantt_data, _repair_dates_on_read


logger = logging.getLogger(__name__)


def _format_formset_errors(formset):
    """Extrait le détail des erreurs du formset (y compris champs cachés et lignes)."""
    details = []
    for err in formset.non_form_errors():
        details.append(str(err))
    for idx, form in enumerate(formset.forms, start=1):
        if not form.errors:
            continue
        label = (
            form.data.get(form.add_prefix("nom"))
            or getattr(form.instance, "nom", "")
            or f"Ligne {idx}"
        )
        for field_name, errs in form.errors.items():
            field_label = "Général" if field_name == "__all__" else field_name
            details.append(f"{label} ({field_label}) : {' '.join(str(e) for e in errs)}")
    return " | ".join(details[:5])


def _inline_context(plan, formset):
    calendar_service = formset.calendar_service
    calendar = calendar_service.to_dict() if calendar_service else None
    calendar_error = " ".join(formset.calendar_error.messages) if formset.calendar_error else ""
    # Réutilise les tâches déjà chargées par le formset lorsqu'il n'est pas lié (GET)
    tasks = getattr(formset, "_tasks_list", None)
    if tasks is None or formset.is_bound:
        tasks = list(plan.taches.order_by("ordre", "pk"))
        rollups_computed = False
        pre_rollup_values = None
    else:
        rollups_computed = True
        pre_rollup_values = getattr(formset, "_pre_rollup_revision_values", None)
    return {
        "plan": plan,
        "formset": formset,
        "work_calendar": calendar,
        "calendar_error": calendar_error,
        "task_link_data": _gantt_data(
            tasks,
            calendar_service,
            rollups_computed=rollups_computed,
            pre_rollup_task_values=pre_rollup_values,
        ),
        "breadcrumb_items": [
            crumb("Accueil", "projets:home"),
            crumb("Plannings", "goplan:liste_plans"),
            crumb("Édition inline"),
        ],
    }


@login_required
def taches_inline(request, plan_id):
    plan = get_object_or_404(
        GPlan.objects.select_related("calendrier").prefetch_related("calendrier__exceptions"),
        pk=plan_id,
    )
    _repair_dates_on_read(request, plan)
    formset = GTaskInlineFormSet(instance=plan, prefix="taches")
    ctx = _inline_context(plan, formset)
    if request.headers.get('HX-Request'):
        return render(request, "goplan/tasks/_taches_inline_content.html", ctx)
    return render(request, "goplan/tasks/taches_inline.html", ctx)


@login_required
@require_POST
def save_taches_inline(request, plan_id):
    plan = get_object_or_404(
        GPlan.objects.select_related("calendrier").prefetch_related("calendrier__exceptions"),
        pk=plan_id,
    )
    formset = GTaskInlineFormSet(request.POST, instance=plan, prefix="taches")
    if formset.is_valid():
        try:
            with transaction.atomic():
                GPlan.objects.select_for_update().get(pk=plan.pk)
                instances = formset.save()
                updated_wbs = recalculate_wbs(plan, instances)
                if updated_wbs:
                    GTask.objects.bulk_update(updated_wbs, ["wbs"])
                links = list(GTaskDependency.objects.filter(
                    successeur_id__in=[task.pk for task in instances],
                ).order_by("pk"))
                seeds = {task.pk for task in instances}
                recalculate_dependencies(
                    plan, instances, links, seeds, calendar=formset.calendar_service,
                )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        except DatabaseError:
            logger.exception("Impossible d'enregistrer les tâches du planning %s", plan.pk)
            messages.error(request, "Erreur lors de l'enregistrement. Vos modifications n'ont pas été sauvegardées.")
        else:
            messages.success(request, f"{len(instances)} tâche(s) enregistrée(s).")
            return redirect("goplan:taches_inline", plan_id=plan.pk)
    else:
        detail = _format_formset_errors(formset)
        msg = "Corrigez les erreurs dans le formulaire."
        if detail:
            msg = f"{msg} ({detail})"
        messages.error(request, msg)
    ctx = _inline_context(plan, formset)
    return render(request, "goplan/tasks/taches_inline.html", ctx)