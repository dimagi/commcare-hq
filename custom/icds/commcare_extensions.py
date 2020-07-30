import os

from django.urls import reverse
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.userreports.extension_points import (
    custom_ucr_expressions,
    custom_ucr_report_filter_values,
    custom_ucr_report_filters,
    static_ucr_data_source_paths,
    static_ucr_reports,
)
from corehq.extensions.extension_points import (
    domain_specific_urls,
    uitab_dropdown_items,
)
from custom.icds.const import ICDS_APPS_ROOT
from custom.icds_core.const import ManageHostedCCZ_urlname


@uitab_dropdown_items.extend(domains=["icds-cas"])
def icds_uitab_dropdown_items(tab, domain, request):
    if tab == 'ApplicationsTab' and toggles.MANAGE_CCZ_HOSTING.enabled_for_request(request):
        return [{
            "title": _("Manage CCZ Hosting"),
            "url": reverse(ManageHostedCCZ_urlname, args=[domain]),
        }]


@domain_specific_urls.extend()
def urls_domain_specific():
    return [
        'custom.icds_reports.urls',
        'custom.icds.urls',
        'custom.icds.data_management.urls',
    ]


@static_ucr_data_source_paths.extend()
def icds_ucr_data_sources():
    return [os.path.join(ICDS_APPS_ROOT, path) for path in [
        "icds_reports/ucr/data_sources/*.json",
        "icds_reports/ucr/data_sources/dashboard/*.json",
    ]]


@static_ucr_reports.extend()
def icds_ucr_reports():
    return [os.path.join(ICDS_APPS_ROOT, path) for path in [
        "icds_reports/ucr/reports/dashboard/*.j,son",
        "icds_reports/ucr/reports/asr/*.json",
        "icds_reports/ucr/reports/asr/ucr_v2/*.json",
        "icds_reports/ucr/reports/mpr/*.json",
        "icds_reports/ucr/reports/mpr/dashboard/*.json",
        "icds_reports/ucr/reports/ls/*.json",
        "icds_reports/ucr/reports/other/*.json",
    ]]


@custom_ucr_expressions.extend()
def icds_ucr_expressions():
    return [
        ('icds_parent_id', 'custom.icds_reports.ucr.expressions.parent_id'),
        ('icds_parent_parent_id', 'custom.icds_reports.ucr.expressions.parent_parent_id'),
        ('icds_get_case_forms_by_date', 'custom.icds_reports.ucr.expressions.get_case_forms_by_date'),
        ('icds_get_all_forms_repeats', 'custom.icds_reports.ucr.expressions.get_all_forms_repeats'),
        ('icds_get_last_form_repeat', 'custom.icds_reports.ucr.expressions.get_last_form_repeat'),
        ('icds_get_case_history', 'custom.icds_reports.ucr.expressions.get_case_history'),
        ('icds_get_case_history_by_date', 'custom.icds_reports.ucr.expressions.get_case_history_by_date'),
        ('icds_get_last_case_property_update', 'custom.icds_reports.ucr.expressions.get_last_case_property_update'),
        ('icds_get_case_forms_in_date', 'custom.icds_reports.ucr.expressions.get_forms_in_date_expression'),
        ('icds_get_app_version', 'custom.icds_reports.ucr.expressions.get_app_version'),
        ('icds_datetime_now', 'custom.icds_reports.ucr.expressions.datetime_now'),
        ('icds_boolean', 'custom.icds_reports.ucr.expressions.boolean_question'),
        ('icds_user_location', 'custom.icds_reports.ucr.expressions.icds_user_location'),
        ('icds_awc_owner_id', 'custom.icds_reports.ucr.expressions.awc_owner_id'),
        ('icds_village_owner_id', 'custom.icds_reports.ucr.expressions.village_owner_id'),
    ]


@custom_ucr_report_filters.extend()
def icds_ucr_report_filters():
    return [
        ('village_choice_list', 'custom.icds_reports.ucr.filter_spec.build_village_choice_list_filter_spec'),
    ]


@custom_ucr_report_filter_values.extend()
def icds_ucr_report_filter_values():
    return [
        ("village_choice_list", "custom.icds_reports.ucr.filter_value.VillageFilterValue"),
    ]
