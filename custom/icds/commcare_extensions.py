import os

from django.urls import reverse
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.userreports.extension_points import static_ucr_data_source_paths, static_ucr_reports
from corehq.extensions.extension_points import uitab_dropdown_items, domain_specific_urls
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
