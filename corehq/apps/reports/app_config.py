from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig


class ReportsModule(AppConfig):
    name = 'corehq.apps.reports'

    def ready(self):
        from corehq.apps.reports import signals  # noqa
