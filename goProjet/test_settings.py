"""Isolated settings for the default Django test command."""

import os

from .settings import *  # noqa: F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

os.environ['DJANGO_SETTINGS_MODULE'] = 'goProjet.test_settings'
