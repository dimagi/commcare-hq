from django.apps import AppConfig


class PillowsAppConfig(AppConfig):
    name = 'corehq.pillows'

    def ready(self):
        from corehq.apps.es.registry import register
        from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO
        from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
        from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
        from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
        from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
        from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX_INFO
        from corehq.pillows.mappings.reportxform_mapping import REPORT_XFORM_INDEX_INFO
        from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
        from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
        from corehq.pillows.mappings.xform_mapping import XFORM_INDEX_INFO

        register(XFORM_INDEX_INFO, "forms")
        register(CASE_INDEX_INFO, "cases")
        register(USER_INDEX_INFO, "users")
        register(DOMAIN_INDEX_INFO, "domains")
        register(APP_INDEX_INFO, "apps")
        register(GROUP_INDEX_INFO, "groups")
        register(SMS_INDEX_INFO, "sms")
        register(REPORT_CASE_INDEX_INFO, "report_cases")
        register(REPORT_XFORM_INDEX_INFO, "report_xforms")
        register(CASE_SEARCH_INDEX_INFO, "case_search")
