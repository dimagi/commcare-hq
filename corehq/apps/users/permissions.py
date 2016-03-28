from collections import namedtuple
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege

FORM_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.ExcelExportReport'
DEID_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.DeidExportReport'
CASE_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.CaseExportReport'


ReportPermission = namedtuple('ReportPermission', ['slug', 'title', 'is_visible'])


def get_extra_permissions():
    from corehq.apps.export.views import FormExportListView, DeIdFormExportListView, CaseExportListView
    yield ReportPermission(
        FORM_EXPORT_PERMISSION, FormExportListView.page_title, lambda domain: True)
    yield ReportPermission(
        DEID_EXPORT_PERMISSION, DeIdFormExportListView.page_title,
        lambda domain: domain_has_privilege(domain, privileges.DEIDENTIFIED_DATA))
    yield ReportPermission(
        CASE_EXPORT_PERMISSION, CaseExportListView.page_title, lambda domain: True)
