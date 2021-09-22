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

        register("forms", XFORM_INDEX_INFO)
        register("cases", CASE_INDEX_INFO)
        register("users", USER_INDEX_INFO)
        register("domains", DOMAIN_INDEX_INFO)
        register("apps", APP_INDEX_INFO)
        register("groups", GROUP_INDEX_INFO)
        register("sms", SMS_INDEX_INFO)
        register("report_cases", REPORT_CASE_INDEX_INFO)
        register("report_xforms", REPORT_XFORM_INDEX_INFO)
        register("case_search", CASE_SEARCH_INDEX_INFO)
