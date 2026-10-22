import base64
import hashlib
import json
import logging
import secrets
from xml.etree import ElementTree as ET

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from ..import_forms import ImportedPlanForm, XmlImportForm
from ..models import GPlan, GTaskAssignment, GTaskDependency
from ..services.mspdi_import import NS, import_mspdi_to_new_plan

logger = logging.getLogger(__name__)
SALT = "goplan.xml-import"
MAX_AGE = 30 * 60


def _fingerprint(plan):
    def values(instance):
        ignored = getattr(instance, "DISPLAY_STATE_FIELDS", ())
        return {field.attname: getattr(instance, field.attname) for field in instance._meta.concrete_fields
                if field.attname not in ignored}

    tasks = list(plan.taches.order_by("pk"))
    payload = [
        values(plan), [values(task) for task in tasks],
        list(GTaskDependency.objects.filter(successeur__plan=plan).order_by("pk").values()),
        list(GTaskAssignment.objects.filter(tache__plan=plan).order_by("pk").values()),
        values(plan.calendrier) if plan.calendrier_id else None,
        list(plan.calendrier.exceptions.order_by("pk").values()) if plan.calendrier_id else [],
    ]
    return hashlib.sha256(json.dumps(payload, cls=DjangoJSONEncoder, sort_keys=True).encode()).hexdigest()


def _summary(imported, xml):
    root = ET.fromstring(xml)
    return {
        "tasks": imported.taches.count(),
        "links": GTaskDependency.objects.filter(successeur__plan=imported).count(),
        "resources": len(root.findall("p:Resources/p:Resource", NS)),
        "assignments": len(root.findall("p:Assignments/p:Assignment", NS)),
    }


@login_required
@require_http_methods(["GET", "POST"])
def import_mspdi(request, plan_id=None):
    target = get_object_or_404(GPlan, pk=plan_id) if plan_id else None
    replacing = target is not None
    upload_form = XmlImportForm(
        request.POST if request.method == "POST" else None,
        request.FILES or None, replacing=replacing,
    )
    context = {"plan": target, "upload_form": upload_form}
    token = request.POST.get("import_token", "") if request.method == "POST" else ""
    if request.method == "POST":
        try:
            if token:
                draft = signing.loads(token, salt=SALT, max_age=MAX_AGE)
                if (draft["user"] != request.user.pk or draft["target"] != plan_id
                        or draft["nonce"] not in request.session.get("goplan_import_drafts", [])):
                    raise ValidationError("Cet import n'est plus disponible. Sélectionnez à nouveau le fichier.")
                xml = base64.b64decode(draft["xml"])
                with transaction.atomic():
                    if replacing:
                        target = get_object_or_404(GPlan.objects.select_for_update(), pk=plan_id)
                        if _fingerprint(target) != draft["revision"]:
                            raise ValidationError("Le planning a changé depuis la sélection du fichier. Relancez l'import.")
                    imported = import_mspdi_to_new_plan(xml)
                    form = ImportedPlanForm(request.POST, imported=imported, replacing=replacing)
                    if form.is_valid():
                        imported.nom = form.cleaned_data["nom"]
                        imported.description = form.cleaned_data["description"]
                        if replacing:
                            # Keep the destination URL/identity, but replace all its planning data.
                            target.taches.all().delete()
                            target.nom = imported.nom
                            target.description = imported.description
                            target.date_debut = imported.date_debut
                            target.date_fin_cible = imported.date_fin_cible
                            target.date_etat = imported.date_etat
                            target.calendrier = imported.calendrier
                            target.content_type = None
                            target.object_id = None
                            target.save()
                            imported.taches.update(plan=target)
                            imported.delete()
                            saved = target
                        else:
                            imported.save(update_fields=["nom", "description"])
                            saved = imported
                        # Session nonce makes a successful confirmation single-use.
                        request.session["goplan_import_drafts"] = [
                            nonce for nonce in request.session.get("goplan_import_drafts", [])
                            if nonce != draft["nonce"]
                        ]
                    else:
                        context.update(final_form=form, import_token=token, summary=_summary(imported, xml))
                        transaction.set_rollback(True)
                        saved = None
                if saved is not None:
                    messages.success(request, f"Planning « {saved.nom} » importé.")
                    return redirect("goplan:taches_inline", plan_id=saved.pk)
            elif upload_form.is_valid():
                xml = upload_form.cleaned_data["fichier"].read()
                with transaction.atomic():
                    imported = import_mspdi_to_new_plan(xml)
                    form = ImportedPlanForm(imported=imported, replacing=replacing)
                    summary = _summary(imported, xml)
                    transaction.set_rollback(True)
                nonce = secrets.token_urlsafe(24)
                draft = {
                    "user": request.user.pk, "target": plan_id, "nonce": nonce,
                    "revision": _fingerprint(target) if replacing else None,
                    "xml": base64.b64encode(xml).decode("ascii"),
                }
                token = signing.dumps(draft, salt=SALT, compress=True)
                if settings.DATA_UPLOAD_MAX_MEMORY_SIZE is not None and len(token) + 16384 > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
                    raise ValidationError("Le fichier est trop volumineux pour la confirmation. Utilisez un XML plus petit.")
                request.session["goplan_import_drafts"] = [
                    *request.session.get("goplan_import_drafts", [])[-9:], nonce,
                ]
                context.update(final_form=form, import_token=token, summary=summary)
        except signing.BadSignature:
            upload_form.add_error(None, "La confirmation d'import est invalide ou a expiré (30 minutes). Relancez l'import.")
            context.pop("final_form", None)
        except ValidationError as error:
            upload_form.add_error(None, error.messages)
            context.pop("final_form", None)
        except DatabaseError:
            logger.exception("Échec de l'import XML vers le planning %s", plan_id)
            upload_form.add_error(None, "Import impossible. Aucune modification n'a été sauvegardée. Relancez l'import.")
            context.pop("final_form", None)
    return render(request, "goplan/plans/import_plan.html", context)
