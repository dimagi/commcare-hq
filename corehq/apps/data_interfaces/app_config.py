from django.apps import AppConfig

from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save

from corehq.form_processor.models import CommCareCaseSQL
from corehq.form_processor.signals import sql_case_post_save

from corehq.apps.data_interfaces.signals import case_changed_receiver


class DataInterfacesAppConfig(AppConfig):
    name = 'data_interfaces'

    def ready(self):
        case_post_save.connect(case_changed_receiver, CommCareCase)
        sql_case_post_save.connect(case_changed_receiver, CommCareCaseSQL)
