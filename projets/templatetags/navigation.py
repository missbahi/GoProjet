from django import template
from django.urls import reverse
from urllib.parse import urlencode

from projets.utils.navigation import notification_origin_token
from projets.models import Notification

register = template.Library()


@register.inclusion_tag('includes/_notification_panel.html', takes_context=True)
def notification_panel(context):
    request = context['request']
    notifications = Notification.objects.filter(
        utilisateur=request.user, lue=False,
    ).select_related('projet').order_by('-date_creation')
    return {
        'notifications': notifications[:5],
        'nb_notifications': notifications.count(),
        'notifications_url': notification_url(context),
    }


def _notification_origin(context, items):
    if 'notification_origin' in context:
        return context['notification_origin']
    return notification_origin_token(items, context.get('request'))


@register.simple_tag(takes_context=True)
def notification_url(context):
    url = reverse('projets:liste_notifications')
    token = _notification_origin(context, context.get('breadcrumb_items', []))
    return f'{url}?{urlencode({"breadcrumb": token})}' if token else url


@register.inclusion_tag('includes/_breadcrumb.html', takes_context=True)
def breadcrumb(context, items=None):
    items = items if items is not None else context.get('breadcrumb_items', [])
    return {
        'items': items,
        'request': context.get('request'),
        'notification_origin': _notification_origin(context, items),
    }