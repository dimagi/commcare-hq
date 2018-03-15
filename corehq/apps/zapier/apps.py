from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig


class ZapierConfig(AppConfig):

    name = 'corehq.apps.zapier'
    verbose_name = 'Zapier'

    def ready(self):
        from .signals import receivers  # noqa
