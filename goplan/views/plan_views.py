# goplan/views/plan_views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
from django.http import HttpResponse

from projets.utils.navigation import crumb

from ..models import GPlan
from ..forms import GPlanForm


@login_required
def liste_plans(request):
    plans = GPlan.objects.all().order_by('-created_at')

    ctx = {
        'plans': plans,
        'breadcrumb_items': [
            crumb("Accueil", "projets:home"),
            crumb("Plannings"), 
        ],
    }

    if request.headers.get('HX-Request'):
        return render(request, 'goplan/plans/_liste_plans_content.html', ctx)

    return render(request, 'goplan/plans/liste_plans.html', ctx)


@login_required
@require_http_methods(["GET", "POST"])
def creer_plan(request):
    """Créer un plan, en page complète ou en modale HTMX."""
    if request.method == 'POST':
        form = GPlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            messages.success(request, f"Plan « {plan.nom} » créé.")

            # ⚡ HTMX : redirection via header (propre)
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('goplan:taches_inline', args=[plan.pk])
                return response

            return redirect('goplan:taches_inline', plan_id=plan.pk)

    else:
        # GET : formulaire vide
        form = GPlanForm(initial={'date_debut': timezone.now().date()})

    template = 'goplan/plans/_modal_plan.html' if request.headers.get('HX-Request') else 'goplan/plans/creer_plan.html'
    return render(request, template, {
        'form': form,
        'plan': None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def modifier_plan(request, plan_id):
    """Modifier un plan, en page complète ou en modale HTMX."""
    plan = get_object_or_404(GPlan, pk=plan_id)

    if request.method == 'POST':
        form = GPlanForm(request.POST, instance=plan)
        if form.is_valid():
            plan = form.save()
            messages.success(request, f"Plan « {plan.nom} » modifié.")

            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Redirect'] = reverse('goplan:taches_inline', args=[plan.pk])
                return response

            return redirect('goplan:taches_inline', plan_id=plan.pk)

    else:
        form = GPlanForm(instance=plan)

    template = 'goplan/plans/_modal_plan.html' if request.headers.get('HX-Request') else 'goplan/plans/modifier_plan.html'
    return render(request, template, {
        'form': form,
        'plan': plan,
    })


@login_required
@require_POST
def supprimer_plan(request, plan_id):
    plan = get_object_or_404(GPlan, pk=plan_id)
    plan.delete()
    messages.success(request, f"Plan « {plan.nom} » supprimé.")
    return redirect('goplan:liste_plans')
