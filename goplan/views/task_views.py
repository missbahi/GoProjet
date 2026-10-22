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
from ..services.calendar import get_calendar_for_plan
from ..services.dependencies import recalculate_dependencies
from .gantt_views import _gantt_data
from ..services.wbs import recalculate_wbs



logger = logging.getLogger(__name__)


def _inline_context(plan, formset):
    calendar_error = ""
    calendar_service = None
    try:
        calendar_service = get_calendar_for_plan(plan)
        calendar = calendar_service.to_dict()
    except ValidationError as error:
        calendar = None
        calendar_error = " ".join(error.messages)
    return {
        "plan": plan,
        "formset": formset,
        "work_calendar": calendar,
        "calendar_error": calendar_error,
        "task_link_data": _gantt_data(list(plan.taches.order_by("ordre", "pk")), calendar_service),
        "breadcrumb_items": [
            crumb("Accueil", "projets:home"),
            crumb("Plannings", "goplan:liste_plans"),
            crumb("Édition inline"),
        ],
    }


@login_required
def taches_inline(request, plan_id):
    plan = get_object_or_404(GPlan.objects.select_related("calendrier"), pk=plan_id)
    formset = GTaskInlineFormSet(instance=plan, prefix="taches")
    ctx = _inline_context(plan, formset)
    if request.headers.get('HX-Request'):
        return render(request, "goplan/tasks/_taches_inline_content.html", ctx)
    return render(request, "goplan/tasks/taches_inline.html", ctx)


@login_required
@require_POST
def save_taches_inline(request, plan_id):
    plan = get_object_or_404(GPlan.objects.select_related("calendrier"), pk=plan_id)
    formset = GTaskInlineFormSet(request.POST, instance=plan, prefix="taches")
    if formset.is_valid():
        try:
            with transaction.atomic():
                GPlan.objects.select_for_update().get(pk=plan.pk)
                instances = formset.save()
                updated_wbs = recalculate_wbs(plan)
                if updated_wbs:
                    GTask.objects.bulk_update(updated_wbs, ["wbs"])
                tasks = list(plan.taches.order_by("ordre", "pk"))
                links = list(GTaskDependency.objects.filter(successeur__plan=plan))
                seeds = {task.pk for task in tasks}
                recalculate_dependencies(plan, tasks, links, seeds)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        except DatabaseError:
            logger.exception("Impossible d'enregistrer les tâches du planning %s", plan.pk)
            messages.error(request, "Erreur lors de l'enregistrement. Vos modifications n'ont pas été sauvegardées.")
        else:
            messages.success(request, f"{len(instances)} tâche(s) enregistrée(s).")
            return redirect("goplan:taches_inline", plan_id=plan.pk)
    else:
        messages.error(request, "Corrigez les erreurs dans le formulaire.")
    ctx = _inline_context(plan, formset)
    return render(request, "goplan/tasks/taches_inline.html", ctx)
