from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig


class ICDSReportsAppConfig(AppConfig):
    name = 'custom.icds_reports'

    def ready(self):
        import custom.icds_reports.reports.reports  # noqa

default_app_config = 'custom.icds_reports.ICDSReportsAppConfig'
