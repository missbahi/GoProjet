import json

from django.contrib import messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from projets.middleware.toast_messages import ToastMessagesMiddleware


class ToastMessagesTests(SimpleTestCase):
    def request(self, method='get', **headers):
        request = getattr(RequestFactory(), method)('/', **headers)
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def run_middleware(self, request, response):
        return ToastMessagesMiddleware(lambda _: response)(request)

    def test_htmx_delivers_django_messages_and_preserves_existing_triggers(self):
        request = self.request(HTTP_HX_REQUEST='true')
        messages.success(request, 'Modifié')
        response = HttpResponse('<form>Errors remain here</form>')
        response['HX-Trigger'] = '{"refreshList":true}'
        self.run_middleware(request, response)
        self.assertEqual(json.loads(response['X-App-Messages']), [
            {'message': 'Modifié', 'type': 'success'},
        ])
        self.assertEqual(response['HX-Trigger'], '{"refreshList":true}')
        self.assertEqual(response.content, b'<form>Errors remain here</form>')
        self.assertTrue(request._messages.used)

    def test_redirect_preserves_messages_until_destination(self):
        request = self.request(HTTP_HX_REQUEST='true')
        messages.success(request, 'Saved')
        response = self.run_middleware(request, HttpResponseRedirect('/destination/'))
        self.assertNotIn('X-App-Messages', response)
        self.assertFalse(request._messages.used)

    def test_classic_page_does_not_consume_messages_in_middleware(self):
        request = self.request()
        messages.warning(request, 'Warning')
        response = self.run_middleware(request, HttpResponse())
        self.assertNotIn('X-App-Messages', response)
        self.assertFalse(request._messages.used)

    def test_json_success_and_error_without_changing_body(self):
        for payload, status, expected_type in (
            ({'success': True, 'message': 'Saved'}, 200, 'success'),
            ({'success': False, 'error': 'Storage failed'}, 500, 'error'),
        ):
            with self.subTest(payload=payload):
                request = self.request('post', HTTP_X_APP_TOAST='true')
                response = JsonResponse(payload, status=status)
                original = response.content
                self.run_middleware(request, response)
                self.assertEqual(json.loads(response['X-App-Messages'])[0]['type'], expected_type)
                self.assertEqual(response.content, original)

    def test_validation_errors_remain_exclusively_in_form_response(self):
        request = self.request('post', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        payload = {'success': False, 'message': 'Correct fields', 'errors': {'title': ['Required']}}
        response = self.run_middleware(request, JsonResponse(payload, status=400))
        self.assertNotIn('X-App-Messages', response)
        self.assertEqual(json.loads(response.content), payload)

    def test_streaming_and_read_only_success_are_not_toasted(self):
        request = self.request(HTTP_X_APP_TOAST='true')
        response = self.run_middleware(request, JsonResponse({'message': 'Read-only', 'success': True}))
        self.assertNotIn('X-App-Messages', response)
        response = self.run_middleware(request, StreamingHttpResponse(iter([b'file'])))
        self.assertNotIn('X-App-Messages', response)
        response.close()

    def test_empty_json_response_and_explicit_warning_level(self):
        request = self.request('post', HTTP_X_APP_TOAST='true')
        response = self.run_middleware(request, HttpResponse(status=204, content_type='application/json'))
        self.assertNotIn('X-App-Messages', response)
        response = self.run_middleware(request, JsonResponse({'message': 'Warning', 'type': 'warning'}))
        self.assertEqual(json.loads(response['X-App-Messages'])[0]['type'], 'warning')

    def test_already_rendered_django_messages_are_still_delivered(self):
        request = self.request(HTTP_HX_REQUEST='true')
        messages.error(request, 'Persistent error')
        list(request._messages)
        response = self.run_middleware(request, HttpResponse())
        self.assertEqual(json.loads(response['X-App-Messages'])[0]['message'], 'Persistent error')

    def test_template_escapes_messages_and_does_not_depend_on_inline_scripts(self):
        request = self.request()
        messages.success(request, '<img src=x onerror=alert(1)>')
        rendered = render_to_string('projets/home/_messages.html', {'messages': request._messages})
        self.assertIn('data-app-message="&lt;img', rendered)
        self.assertNotIn('<script>', rendered)
        self.assertIn('<noscript>', rendered)

    def test_shared_action_messages_keep_only_errors_and_warnings_permanent(self):
        request = self.request()
        messages.success(request, 'Action succeeded')
        messages.info(request, 'Action information')
        messages.warning(request, 'Needs attention')
        messages.error(request, 'Form error')
        rendered = render_to_string('projets/home/_action_messages.html', {'messages': request._messages})
        self.assertIn('data-app-message="Action succeeded"', rendered)
        self.assertIn('data-app-message="Action information"', rendered)
        self.assertNotIn('app-alert-success', rendered)
        self.assertEqual(rendered.count('data-persistent-action-message'), 2)
        self.assertIn('app-alert-error', rendered)
        self.assertIn('app-alert-warning', rendered)
        self.assertNotIn('alert-auto-dismiss', rendered)

    def test_active_message_templates_use_the_shared_renderer(self):
        from django.template.loader import get_template

        templates = (
            'suivi/_suivi_execution_content.html',
            'utilisateurs/_modifier_utilisateur_content.html',
            'situations/_formulaire_situation_mensuelle.html',
            'decomptes/_validation_attachement_content.html',
            'decomptes/_validation_technique_attachement_content.html',
            'decomptes/_attachement_form_content.html',
            'decomptes/_detail_decompte_content.html',
            'decomptes/_liste_decomptes_content.html',
            'rapports/ajouter_rapport_journalier.html',
            'rapports/modifier_rapport_journalier.html',
            'lots/saisie_bordereau.html',
        )
        for template in templates:
            with self.subTest(template=template):
                source = get_template(f'projets/{template}').template.source
                self.assertIn('projets/home/_action_messages.html', source)
                self.assertNotIn('for message in messages', source)
