import os
import sys
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

import manage


class TestSettingsIsolationTests(SimpleTestCase):
    def test_manage_uses_isolated_settings_for_tests_by_default(self):
        for configured in (None, 'goProjet.settings'):
            with self.subTest(configured=configured), patch.dict(os.environ), \
                 patch.object(sys, 'argv', ['manage.py', 'test']), \
                 patch('django.core.management.execute_from_command_line') as execute:
                if configured is None:
                    os.environ.pop('DJANGO_SETTINGS_MODULE', None)
                else:
                    os.environ['DJANGO_SETTINGS_MODULE'] = configured
                manage.main()
                self.assertEqual(os.environ['DJANGO_SETTINGS_MODULE'], 'goProjet.test_settings')
                execute.assert_called_once_with(sys.argv)

    def test_other_commands_and_explicit_settings_are_preserved(self):
        for command, configured, expected in (
            ('runserver', None, 'goProjet.settings'),
            ('test', 'custom.settings', 'custom.settings'),
        ):
            with self.subTest(command=command), patch.dict(os.environ), \
                 patch.object(sys, 'argv', ['manage.py', command]), \
                 patch('django.core.management.execute_from_command_line'):
                if configured is None:
                    os.environ.pop('DJANGO_SETTINGS_MODULE', None)
                else:
                    os.environ['DJANGO_SETTINGS_MODULE'] = configured
                manage.main()
                self.assertEqual(os.environ['DJANGO_SETTINGS_MODULE'], expected)

    def test_isolated_settings_configure_an_in_memory_database(self):
        with patch.dict(os.environ):
            from goProjet import test_settings

        database = test_settings.DATABASES['default']
        self.assertEqual(database['ENGINE'], 'django.db.backends.sqlite3')
        name = database['NAME']
        self.assertTrue(name == ':memory:' or (
            name.startswith('file:memorydb_') and 'mode=memory' in name
        ))
