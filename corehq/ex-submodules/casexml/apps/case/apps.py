
from django.apps import AppConfig


class CaseXMLModule(AppConfig):
    name = 'casexml.apps.case'

    def ready(self):
        from casexml.apps.case.signals import connect_signals
        connect_signals()
