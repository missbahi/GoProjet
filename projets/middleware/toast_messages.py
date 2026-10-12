import json

from django.contrib.messages import get_messages
from django.utils.cache import patch_vary_headers


class ToastMessagesMiddleware:
    """Deliver action messages without changing response bodies or form errors."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        asynchronous = (
            request.headers.get('HX-Request') == 'true'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.headers.get('X-App-Toast') == 'true'
        )
        # Redirect messages must survive until the destination is rendered.
        if not asynchronous or 300 <= response.status_code < 400 or response.streaming:
            return response

        notifications = [
            {'message': str(message), 'type': message.level_tag or 'info'}
            for message in get_messages(request)
        ]
        if (
            'application/json' in response.get('Content-Type', '')
            and response.content
            and (request.method not in ('GET', 'HEAD') or response.status_code >= 400)
        ):
            payload = json.loads(response.content)
            if isinstance(payload, dict) and not payload.get('errors'):
                text = payload.get('message') or payload.get('error')
                failed = response.status_code >= 400 or payload.get('success') is False
                if isinstance(text, str) and (failed or request.method not in ('GET', 'HEAD')):
                    level = payload.get('message_type', payload.get('type'))
                    if failed:
                        level = 'error'
                    elif level not in ('success', 'warning', 'info'):
                        level = 'success'
                    notifications.append({'message': text, 'type': level})

        if notifications:
            response['X-App-Messages'] = json.dumps(notifications, ensure_ascii=True)
            patch_vary_headers(response, ['HX-Request', 'X-Requested-With', 'X-App-Toast'])
        return response
