from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig

from corehq.apps.data_interfaces.signals import case_changed_receiver


class DataInterfacesAppConfig(AppConfig):
    name = 'corehq.apps.data_interfaces'

    def ready(self):
        from casexml.apps.case.models import CommCareCase
        from casexml.apps.case.signals import case_post_save
        from corehq.form_processor.models import CommCareCaseSQL
        from corehq.form_processor.signals import sql_case_post_save

        case_post_save.connect(case_changed_receiver, CommCareCase,
                               dispatch_uid="data_interfaces_case_receiver")
        sql_case_post_save.connect(case_changed_receiver, CommCareCaseSQL,
                                   dispatch_uid="data_interfaces_sql_case_receiver")
