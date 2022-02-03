from django.apps import AppConfig

from corehq.apps.data_interfaces.signals import case_changed_receiver


class DataInterfacesAppConfig(AppConfig):
    name = 'corehq.apps.data_interfaces'

    def ready(self):
        from corehq.form_processor.models import CommCareCase
        from corehq.form_processor.signals import sql_case_post_save

        sql_case_post_save.connect(case_changed_receiver, CommCareCase,
                                   dispatch_uid="data_interfaces_sql_case_receiver")
