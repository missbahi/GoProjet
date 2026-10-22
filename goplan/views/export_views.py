# goplan/views/export_views.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.text import slugify

from ..models import GPlan
from ..services.mspdi_export import export_plan_to_mspdi


@login_required
def export_mspdi(request, plan_id):
    plan = get_object_or_404(GPlan, pk=plan_id)
    try:
        xml = export_plan_to_mspdi(plan)
    except Exception:
        # On laisse Django logger ; pour l'utilisateur, un 500 explicite
        raise

    filename = (slugify(plan.nom) or f"plan-{plan.pk}") + ".xml"
    response = HttpResponse(xml, content_type="application/xml; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response