from django.apps import AppConfig


class ICDSReportsAppConfig(AppConfig):
    name = 'custom.icds_reports'

    def ready(self):
        import custom.icds_reports.reports.reports  # noqa

default_app_config = 'custom.icds_reports.ICDSReportsAppConfig'
