from collections import namedtuple

from django.utils.translation import gettext_noop

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege

VIEW_SUBMISSION_HISTORY_PERMISSION = 'corehq.apps.reports.standard.inspect.SubmitHistory'

FORM_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.ExcelExportReport'
DEID_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.DeidExportReport'
CASE_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.CaseExportReport'
ODATA_FEED_PERMISSION = 'corehq.apps.reports.standard.export.ODataFeedListView'
SMS_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.SMSExportReport'
PAYMENTS_REPORT_PERMISSION = 'corehq.apps.integration.payments.views.PaymentsVerificationReportView'

EXPORT_PERMISSIONS = {
    FORM_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    CASE_EXPORT_PERMISSION,
    ODATA_FEED_PERMISSION,
}

COMMCARE_ANALYTICS_SQL_LAB = "sql_lab"
COMMCARE_ANALYTICS_DATASET_EDITOR = "dataset_editor"

COMMCARE_ANALYTICS_USER_ROLES = [
    COMMCARE_ANALYTICS_SQL_LAB,
    COMMCARE_ANALYTICS_DATASET_EDITOR,
]

ReportPermission = namedtuple('ReportPermission', ['slug', 'title', 'is_visible'])


def get_extra_permissions():
    from corehq.apps.export.views.list import (
        FormExportListView,
        CaseExportListView,
        ODataFeedListView,
    )
    from corehq.apps.export.views.download import DownloadNewSmsExportView
    from corehq.apps.integration.payments.views import PaymentsVerificationReportView

    yield ReportPermission(
        FORM_EXPORT_PERMISSION, FormExportListView.page_title, lambda domain_obj: True)
    yield ReportPermission(
        DEID_EXPORT_PERMISSION, gettext_noop("Export De-Identified Data"),
        lambda domain_obj: domain_has_privilege(domain_obj, privileges.DEIDENTIFIED_DATA))
    yield ReportPermission(
        CASE_EXPORT_PERMISSION, CaseExportListView.page_title, lambda domain: True)
    yield ReportPermission(
        SMS_EXPORT_PERMISSION, DownloadNewSmsExportView.page_title, lambda domain: True)
    yield ReportPermission(
        ODATA_FEED_PERMISSION, ODataFeedListView.page_title,
        lambda domain_obj: domain_has_privilege(domain_obj, privileges.ODATA_FEED)
    )
    yield ReportPermission(
        PAYMENTS_REPORT_PERMISSION,
        PaymentsVerificationReportView.page_title,
        lambda domain_obj: toggles.MTN_MOBILE_WORKER_VERIFICATION.enabled(domain_obj.name)
    )


def can_download_data_files(domain, couch_user):
    return _has_data_file_permission(domain, couch_user, read_only=True)


def can_upload_data_files(domain, couch_user):
    return _has_data_file_permission(domain, couch_user, read_only=False)


def _has_data_file_permission(domain, couch_user, read_only=True):
    if not domain_has_privilege(domain, privileges.DATA_FILE_DOWNLOAD):
        return False

    return (
        couch_user.can_edit_file_dropzone()
        or (read_only and couch_user.can_view_file_dropzone())
    )


def can_view_sms_exports(couch_user, domain):
    return has_permission_to_view_report(
        couch_user, domain, SMS_EXPORT_PERMISSION
    )


def has_permission_to_view_report(couch_user, domain, report_to_check):
    from corehq.apps.users.decorators import get_permission_name
    from corehq.apps.users.models import HqPermissions
    return couch_user.has_permission(
        domain,
        get_permission_name(HqPermissions.view_report),
        data=report_to_check
    )


def can_access_payments_report(couch_user, domain):
    return has_permission_to_view_report(couch_user, domain, PAYMENTS_REPORT_PERMISSION)
