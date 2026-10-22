import hashlib
import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from projets.utils.navigation import crumb

from ..forms import GPlanAppearanceForm, GPlanPrintSettingsForm, GTaskGanttForm
from ..models import PRINT_TEXT_VARIABLES, GPlan, GPlanPrintSettings, GTask, GTaskDependency
from ..services.calendar import get_calendar_for_plan
from ..services.dependencies import possible_predecessors, recalculate_dependencies, recalculate_group_rollups
from ..services.wbs import recalculate_wbs

from collections import defaultdict


logger = logging.getLogger(__name__)


def _appearance_data(plan):
    values = {name: getattr(plan, name) for name in GPlanAppearanceForm.Meta.fields}
    revision = hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()
    return {
        "values": values, "revision": revision,
        "defaults": {name: GPlan._meta.get_field(name).get_default() for name in values},
    }


@login_required
@require_POST
def save_gantt_appearance(request, plan_id):
    try:
        with transaction.atomic():
            plan = get_object_or_404(GPlan.objects.select_for_update(), pk=plan_id)
            if request.POST.get("revision") != _appearance_data(plan)["revision"]:
                return JsonResponse({"errors": {
                    "__all__": ["L'apparence a changé. Rechargez la page avant d'appliquer vos réglages."],
                }}, status=409)
            form = GPlanAppearanceForm(request.POST, instance=plan)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            plan = form.save(commit=False)
            plan.save(update_fields=[*form.Meta.fields, "updated_at"])
            return JsonResponse(_appearance_data(plan))
    except DatabaseError:
        logger.exception("Échec de l'enregistrement de l'apparence du planning %s", plan_id)
        return JsonResponse({"errors": {
            "__all__": ["Impossible d'enregistrer l'apparence. Aucune modification sauvegardée."],
        }}, status=500)


LINK_LABELS = {"FS": "FD", "SS": "DD", "FF": "FF", "SF": "DF"}


def _print_settings_data(plan):
    try:
        settings = plan.print_settings
    except GPlanPrintSettings.DoesNotExist:
        settings = GPlanPrintSettings(plan=plan)
    names = list(GPlanPrintSettingsForm.base_fields)
    values = {name: getattr(settings, name) for name in names}
    values = json.loads(json.dumps(values, cls=DjangoJSONEncoder))
    default = GPlanPrintSettings(plan=plan)
    return {
        "values": values,
        "defaults": json.loads(json.dumps(
            {name: getattr(default, name) for name in names}, cls=DjangoJSONEncoder,
        )),
        "saved": settings.pk is not None,
        "revision": hashlib.sha256(json.dumps(
            [settings.pk, values], sort_keys=True,
        ).encode()).hexdigest(),
    }


def _print_rows(tasks):
    """Valeurs des colonnes imprimables, après les cumuls de groupes calculés en mémoire."""
    ordered, _ = _ordered_tasks(tasks)
    by_id = {task.pk: task for task in tasks}
    predecessors = defaultdict(list)
    for link in _plan_links(tasks):
        source = by_id.get(link.predecesseur_id)
        reference = (source.code or source.wbs or f"#{source.pk}") if source else f"#{link.predecesseur_id}"
        suffix = "" if link.type_lien == "FS" else LINK_LABELS.get(link.type_lien, link.type_lien)
        if link.decalage_jours:
            suffix += f"{link.decalage_jours:+d} j"
        predecessors[link.successeur_id].append(reference + suffix)
    return [{
        "id": str(task.pk),
        "parent_id": str(task.parent_id) if task.parent_id else "",
        "code": task.code,
        "nom": task.nom,
        "level": level,
        "type": task.type_tache,
        "duree": float(task.duree),
        "debut": task.date_debut.isoformat() if task.date_debut else "",
        "fin": task.date_fin.isoformat() if task.date_fin else "",
        "avancement": float(task.avancement),
        "predecesseurs": "; ".join(predecessors.get(task.pk, [])),
        "replie": task.replie,
    } for task, level in ordered]


@login_required
@require_POST
def toggle_task_fold(request, plan_id):
    """Mémorise l'état replié d'un groupe (simple état d'affichage, sans contrôle de révision)."""
    plan = get_object_or_404(GPlan, pk=plan_id)
    folded = request.POST.get("replie") in ("1", "true", "on")
    try:
        task_id = int(request.POST.get("task", ""))
    except ValueError:
        return JsonResponse({"errors": {"task": ["Tâche invalide."]}}, status=400)
    task = get_object_or_404(GTask.objects.only("pk"), plan=plan, pk=task_id)
    GTask.objects.filter(pk=task.pk).update(replie=folded)
    return JsonResponse({"task": str(task.pk), "replie": folded})


def _print_settings_response(request, plan_id, reset):
    try:
        with transaction.atomic():
            plan = get_object_or_404(GPlan.objects.select_for_update(), pk=plan_id)
            if request.POST.get("revision") != _print_settings_data(plan)["revision"]:
                return JsonResponse({"errors": {"__all__": [
                    "Les réglages d'impression ont été modifiés ailleurs. Rechargez la page.",
                ]}}, status=409)
            if reset:
                GPlanPrintSettings.objects.filter(plan=plan).delete()
                plan = GPlan.objects.get(pk=plan.pk)
            else:
                instance = GPlanPrintSettings.objects.filter(plan=plan).first() or GPlanPrintSettings(plan=plan)
                form = GPlanPrintSettingsForm(request.POST, instance=instance)
                if not form.is_valid():
                    return JsonResponse({"errors": {
                        field: [error["message"] for error in errors]
                        for field, errors in form.errors.get_json_data().items()
                    }}, status=400)
                form.save()
                plan = GPlan.objects.get(pk=plan.pk)
            return JsonResponse(_print_settings_data(plan))
    except DatabaseError:
        logger.exception("Échec de l'enregistrement des réglages d'impression du planning %s", plan_id)
        return JsonResponse({"errors": {"__all__": [
            "Impossible d'enregistrer les réglages d'impression. Aucune modification sauvegardée.",
        ]}}, status=500)


@login_required
@require_POST
def save_print_settings(request, plan_id):
    return _print_settings_response(request, plan_id, reset=False)


@login_required
@require_POST
def reset_print_settings(request, plan_id):
    return _print_settings_response(request, plan_id, reset=True)


def _ordered_tasks(tasks):
    children = {}
    for task in tasks:
        children.setdefault(task.parent_id, []).append(task)

    ordered = []
    visited = set()

    def append_subtree(task, level):
        pending = [(task, level)]
        while pending:
            current, depth = pending.pop()
            if current.pk in visited:
                continue
            visited.add(current.pk)
            ordered.append((current, depth))
            pending.extend(
                (child, depth + 1) for child in reversed(children.get(current.pk, []))
            )

    for task in children.get(None, []):
        append_subtree(task, 0)
    invalid_hierarchy = len(visited) != len(tasks)
    # Keep legacy orphaned/cyclic rows visible instead of losing them.
    for task in tasks:
        if task.pk not in visited:
            append_subtree(task, 0)

    return ordered, invalid_hierarchy


def _revision(tasks):
    values = [
        {field.attname: getattr(task, field.attname) for field in GTask._meta.concrete_fields
         if field.attname not in GTask.DISPLAY_STATE_FIELDS}
        for task in tasks
    ]
    links = list(_plan_links(tasks).values(
        "pk", "predecesseur_id", "successeur_id", "type_lien", "decalage_jours",
    ))
    return hashlib.sha256(json.dumps(
        [values, links], cls=DjangoJSONEncoder, sort_keys=True,
    ).encode()).hexdigest()


def _plan_links(tasks):
    return GTaskDependency.objects.filter(
        successeur_id__in=[task.pk for task in tasks],
    ).order_by("pk")


def _gantt_data(tasks, calendar=None):
    revision = _revision(tasks)
    ordered, invalid_hierarchy = _ordered_tasks(tasks)
    if calendar is not None and not invalid_hierarchy:
        recalculate_group_rollups(None, tasks, calendar, persist=False)
    dated = [
        (task, level) for task, level in ordered
        if task.date_debut and task.date_fin and task.date_fin >= task.date_debut
    ]
    dated_ids = {task.pk for task, _ in dated}
    dependencies = {}
    links = list(_plan_links(tasks))
    choices = possible_predecessors(tasks, links)
    for link in links:
        if link.predecesseur_id in dated_ids and link.successeur_id in dated_ids:
            dependencies.setdefault(link.successeur_id, []).append(str(link.predecesseur_id))

    data = [{
        "id": str(task.pk),
        "name": str(task),
        "start": task.date_debut.isoformat(),
        "end": task.date_fin.isoformat(),
        "duration": float(task.duree),
        "progress": float(task.avancement),
        "level": level,
        "type": task.type_tache,
        "critical": task.est_critique,
        "color": task.couleur,
        "dependencies": dependencies.get(task.pk, []),
    } for task, level in dated]
    editable = [{
        "id": str(task.pk), "label": str(task),
        "parent_id": str(task.parent_id) if task.parent_id else "",
        "possible_predecessors": [
            str(candidate.pk) for candidate, _ in ordered
            if candidate.pk in choices[task.pk] and candidate.pk in dated_ids
        ],
        "values": {
            name: getattr(task, name)
            for name in GTaskGanttForm.Meta.fields
        },
    } for task, _ in ordered]
    return {
        'tasks': data,
        'editable': editable,
        'revision': revision,
        'links': [{
            'id': str(link.pk),
            'predecessor': str(link.predecesseur_id),
            'successor': str(link.successeur_id),
            'type': link.type_lien,
            'lag': link.decalage_jours,
        } for link in links],
        'undated_count': len(tasks) - len(dated),
        'invalid_hierarchy': invalid_hierarchy,
        'collapsed': [str(task.pk) for task in tasks if task.replie],
    }


def _gantt_context(plan, tasks):
    calendar_error = ""
    calendar_service = None
    try:
        calendar_service = get_calendar_for_plan(plan)
        calendar = calendar_service.to_dict()
    except ValidationError as error:
        calendar = None
        calendar_error = " ".join(error.messages)
    data = _gantt_data(tasks, calendar_service)
    breadcrumb_items = [
                crumb("Accueil", "projets:home"),
                crumb("Plannings", "goplan:liste_plans"),
                crumb(plan.nom, "goplan:taches_inline", args=[plan.pk]),
                crumb("Gantt"),
            ]
    ctx = {
        'plan': plan,
        'gantt_tasks': data['tasks'],
        'gantt_data': data,
        'task_form': GTaskGanttForm(),
        'appearance_form': GPlanAppearanceForm(instance=plan),
        'appearance_data': _appearance_data(plan),
        'work_calendar': calendar,
        'calendar_error': calendar_error,
        'undated_count': data['undated_count'],
        'invalid_hierarchy': data['invalid_hierarchy'],
        'breadcrumb_items': breadcrumb_items,
    }
    return ctx


@login_required
@require_GET
def gantt_plan(request, plan_id):
    plan = get_object_or_404(GPlan.objects.select_related("calendrier"), pk=plan_id)
    ctx = _gantt_context(plan, list(plan.taches.order_by("ordre", "pk")))
    if request.headers.get('HX-Request'):
        return render(request, 'goplan/gantt/_gantt_plan_content.html', ctx)
    
    return render(request, 'goplan/gantt/gantt_plan.html', ctx)


@login_required
@require_GET
def apercu_plan(request, plan_id):
    plan = get_object_or_404(GPlan.objects.select_related("calendrier"), pk=plan_id)
    tasks = list(plan.taches.order_by("ordre", "pk"))
    context = _gantt_context(plan, tasks)
    if request.GET.get("mode") != "tasks":
        context["print_settings"] = _print_settings_data(plan)
        context["print_rows"] = _print_rows(tasks)
        context["print_variables"] = PRINT_TEXT_VARIABLES
        context["font_choices"] = GPlanPrintSettings.Police.choices
        context["background_presets"] = GPlanPrintSettings.BACKGROUND_PRESETS
        context["print_context"] = {
            "plan": plan.nom,
            "description": plan.description or "",
            "date_etat": plan.date_etat.isoformat() if plan.date_etat else "",
            "calendrier": plan.calendrier.nom if plan.calendrier else "Standard (Lun–Ven)",
        }
        return render(request, "goplan/plans/apercu_plan.html", context)
    ordered, invalid_hierarchy = _ordered_tasks(tasks)

    # Prédécesseurs
    links = GTaskDependency.objects.filter(
        successeur__in=[t.pk for t in tasks],
    ).select_related("predecesseur").order_by("predecesseur__wbs", "pk")
    preds_by_task = defaultdict(list)
    for link in links:
        preds_by_task[link.successeur_id].append(link)

    total_duration = 0.0
    total_tasks = total_groupes = total_jalons = 0
    date_min = date_max = None
    undated_count = 0

    for task, level in ordered:
        # Enrichissement pour le template
        task.wbs = task.wbs or ""
        task.predecessors_display = preds_by_task.get(task.pk, [])

        if task.type_tache == GTask.Type.GROUPE:
            total_groupes += 1
        elif task.type_tache == GTask.Type.JALON:
            total_jalons += 1
        else:
            total_tasks += 1
            total_duration += float(task.duree or 0)

        if task.date_debut and task.date_fin:
            if date_min is None or task.date_debut < date_min:
                date_min = task.date_debut
            if date_max is None or task.date_fin > date_max:
                date_max = task.date_fin
        else:
            undated_count += 1

    # Fallbacks si aucune date n'est calculable
    date_min = date_min or plan.date_debut
    date_max = date_max or plan.date_fin_cible or plan.date_debut

    # Écart avec la cible
    ecart_cible = 0
    if plan.date_fin_cible and date_max:
        ecart_cible = (date_max - plan.date_fin_cible).days

    # Nom du calendrier
    calendar_nom = plan.calendrier.nom if plan.calendrier_id else "Standard (Lun–Ven)"
 
    return render(request, "goplan/plans/apercu_tasks.html", {
        "plan": plan,
        "tasks_ordered": ordered,
        "invalid_hierarchy": invalid_hierarchy,
        "undated_count": undated_count,
        "total_tasks": total_tasks,
        "total_groupes": total_groupes,
        "total_jalons": total_jalons,
        "total_duration": total_duration,
        "date_min": date_min,
        "date_max": date_max,
        "ecart_cible": ecart_cible,
        "calendar_nom": calendar_nom,
        "calendar_error": context["calendar_error"],
        "formats": [("A4","A4"), ("A3","A3"), ("A2","A2"), ("A1","A1"), ("A0","A0")],
    })

@login_required
@require_POST
def save_gantt_task(request, plan_id):
    try:
        with transaction.atomic():
            plan = get_object_or_404(GPlan.objects.select_for_update(), pk=plan_id,)
            tasks = list(plan.taches.select_for_update().order_by("ordre", "pk"))

            if request.POST.get("revision") != _revision(tasks):
                return JsonResponse({
                    "errors": {"__all__": ["Le planning a changé. Rechargez la page avant d'enregistrer."]},
                }, status=409)
            
            ordered, invalid = _ordered_tasks(tasks)

            if invalid:
                return JsonResponse({
                    "errors": {"__all__": ["Corrigez la hiérarchie dans l'éditeur inline avant d'enregistrer."]},
                }, status=400)
            
            task_id = request.POST.get("task_id", "")
            by_id = {str(task.pk): task for task in tasks}
            
            if task_id and task_id not in by_id:
                return JsonResponse({"errors": {"__all__": ["Tâche absente de ce planning."]}}, status=404)
            
            position = request.POST.get("position", "end")
            reference = by_id.get(request.POST.get("reference_id", ""))

            if not task_id and (position not in ("end", "before") or (position == "before" and not reference)):
                return JsonResponse({"errors": {"__all__": ["Position d'insertion invalide."]}}, status=400)
            try:
                calendar = get_calendar_for_plan(plan)
            except ValidationError as error:
                return JsonResponse({"errors": {"__all__": error.messages}}, status=400)
            
            instance = by_id[task_id] if task_id else GTask(plan=plan)
            form = GTaskGanttForm(request.POST, instance=instance, calendar_service=calendar)

            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            
            task = form.save(commit=False)

            if not task_id:
                sequence = [item for item, _ in ordered]
                if position == "before":
                    task.parent_id = reference.parent_id
                    sequence.insert(sequence.index(reference), task)
                else:
                    task.parent_id = None
                    sequence.append(task)
                task.save()
                for index, item in enumerate(sequence):
                    item.ordre = index
                GTask.objects.bulk_update(sequence, ["ordre"])
            else:
                task.save()

            refreshed_tasks = list(plan.taches.order_by("ordre", "pk"))
            group_changes = recalculate_group_rollups(plan, refreshed_tasks, calendar)

            recalculate_dependencies(plan, refreshed_tasks, 
                                     list(_plan_links(refreshed_tasks)), {task.pk, *group_changes},)

            updated_wbs = recalculate_wbs(plan, list(plan.taches.order_by("ordre", "pk")))
            if updated_wbs:
                GTask.objects.bulk_update(updated_wbs, ["wbs"])

            data = _gantt_data(list(plan.taches.order_by("ordre", "pk")), calendar)
            data["saved_id"] = str(task.pk)

            return JsonResponse(data)
        
    except ValidationError as error:
        return JsonResponse({"errors": {"__all__": error.messages}}, status=400)
    except DatabaseError:
        logger.exception("Impossible d'enregistrer une tâche du Gantt %s", plan_id)
        return JsonResponse({
            "errors": {"__all__": ["Enregistrement impossible. Vos modifications sont conservées dans le formulaire."]},
        }, status=500)


@login_required
@require_POST
def delete_gantt_task(request, plan_id):
    try:
        with transaction.atomic():
            plan = get_object_or_404(GPlan.objects.select_for_update(), pk=plan_id)
            tasks = list(plan.taches.select_for_update().order_by("ordre", "pk"))
            if request.POST.get("revision") != _revision(tasks):
                return JsonResponse({"errors": {"__all__": [
                    "Le planning a changé. Rechargez la page avant de supprimer.",
                ]}}, status=409)
            ordered, invalid = _ordered_tasks(tasks)
            if invalid:
                raise ValidationError("Corrigez la hiérarchie avant de supprimer une tâche.")
            task = next((item for item in tasks if str(item.pk) == request.POST.get("task_id")), None)
            if task is None:
                return JsonResponse({"errors": {"__all__": ["Tâche absente de ce planning."]}}, status=404)
            removed = {task.pk}
            for item, _ in ordered:
                if item.parent_id in removed:
                    removed.add(item.pk)
            if GTask.objects.filter(parent_id__in=removed).exclude(plan=plan).exists():
                raise ValidationError("Des sous-tâches appartiennent à un autre planning. Corrigez leurs parents.")
            successors = set(GTaskDependency.objects.filter(
                predecesseur_id__in=removed, successeur__plan=plan,
            ).exclude(successeur_id__in=removed).values_list("successeur_id", flat=True))
            task.delete()
            remaining = list(plan.taches.order_by("ordre", "pk"))
            for index, item in enumerate(remaining):
                item.ordre = index
                if item.pk == task.parent_id and item.type_tache == GTask.Type.GROUPE:
                    if not any(child.parent_id == item.pk for child in remaining):
                        item.type_tache = GTask.Type.TACHE

            if remaining:
                GTask.objects.bulk_update(remaining, ["ordre", "type_tache"])
                
            calendar = get_calendar_for_plan(plan)
            group_changes = recalculate_group_rollups(plan, remaining, calendar)
            recalculate_dependencies(plan, remaining, list(_plan_links(remaining)), successors | group_changes)
            updated_wbs = recalculate_wbs(plan, remaining)
            if updated_wbs:
                GTask.objects.bulk_update(updated_wbs, ["wbs"])

            data = _gantt_data(list(plan.taches.order_by("ordre", "pk")), calendar)
            data["deleted_count"] = len(removed)
            return JsonResponse(data)
    except ValidationError as error:
        return JsonResponse({"errors": {"__all__": error.messages}}, status=400)
    except DatabaseError:
        logger.exception("Impossible de supprimer une tâche du Gantt %s", plan_id)
        return JsonResponse({"errors": {"__all__": [
            "Suppression impossible. Aucune modification n'a été appliquée.",
        ]}}, status=500)


@login_required
@require_POST
def save_gantt_link(request, plan_id):
    try:
        with transaction.atomic():
            plan = get_object_or_404(GPlan.objects.select_for_update(), pk=plan_id)
            tasks = list(plan.taches.select_for_update().order_by("ordre", "pk"))
            if request.POST.get("revision") != _revision(tasks):
                return JsonResponse({"errors": {"__all__": [
                    "Le planning ou ses liaisons ont changé. Rechargez la page.",
                ]}}, status=409)
            if _ordered_tasks(tasks)[1]:
                raise ValidationError("Corrigez la hiérarchie avant de gérer les liaisons.")
            by_id = {str(task.pk): task for task in tasks}
            successor = by_id.get(request.POST.get("successor"))
            predecessor = by_id.get(request.POST.get("predecessor"))
            if not successor or not predecessor or successor.pk == predecessor.pk:
                raise ValidationError("Choisissez deux tâches distinctes de ce planning.")
            action = request.POST.get("action")
            if action == "delete":
                deleted, _ = GTaskDependency.objects.filter(
                    predecesseur=predecessor, successeur=successor,
                ).delete()
                if not deleted:
                    raise ValidationError("Cette liaison n'existe plus.")
            elif action == "save":
                choices = possible_predecessors(tasks, list(_plan_links(tasks)))
                if predecessor.pk not in choices[successor.pk]:
                    raise ValidationError(
                        "Liaison interdite : tâche identique, parent, ancêtre, descendant ou cycle de dépendances."
                    )
                link_type = request.POST.get("type")
                if link_type not in GTaskDependency.Type.values:
                    raise ValidationError("Type de liaison invalide.")
                try:
                    lag = int(request.POST.get("lag", ""))
                except (ValueError, TypeError):
                    raise ValidationError("Le décalage doit être un nombre entier de jours ouvrés.")
                if not -36500 <= lag <= 36500:
                    raise ValidationError("Le décalage doit être compris entre -36500 et 36500 jours ouvrés.")
                if not predecessor.date_debut or not predecessor.date_fin:
                    raise ValidationError("Renseignez les dates du prédécesseur avant de créer une liaison.")
                GTaskDependency.objects.update_or_create(
                    predecesseur=predecessor, successeur=successor,
                    defaults={"type_lien": link_type, "decalage_jours": lag},
                )
            else:
                raise ValidationError("Action de liaison invalide.")
            calendar = get_calendar_for_plan(plan)
            group_changes = recalculate_group_rollups(plan, tasks, calendar)
            recalculate_dependencies(
                plan, tasks, list(_plan_links(tasks)), {successor.pk, *group_changes},
            )
            return JsonResponse(_gantt_data(list(plan.taches.order_by("ordre", "pk")), calendar))
    except ValidationError as error:
        return JsonResponse({"errors": {"__all__": error.messages}}, status=400)
    except DatabaseError:
        logger.exception("Impossible d'enregistrer une liaison du planning %s", plan_id)
        return JsonResponse({"errors": {"__all__": [
            "Impossible d'enregistrer la liaison. Aucune modification n'a été appliquée.",
        ]}}, status=500)