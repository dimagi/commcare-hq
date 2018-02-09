from __future__ import absolute_import
from collections import namedtuple
from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege

FORM_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.ExcelExportReport'
DEID_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.DeidExportReport'
CASE_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.CaseExportReport'
SMS_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.SMSExportReport'

EXPORT_PERMISSIONS = {FORM_EXPORT_PERMISSION, DEID_EXPORT_PERMISSION, CASE_EXPORT_PERMISSION}

ReportPermission = namedtuple('ReportPermission', ['slug', 'title', 'is_visible'])


def get_extra_permissions():
    from corehq.apps.export.views import (
        FormExportListView, DeIdFormExportListView, CaseExportListView, DownloadNewSmsExportView
    )
    yield ReportPermission(
        FORM_EXPORT_PERMISSION, FormExportListView.page_title, lambda domain: True)
    yield ReportPermission(
        DEID_EXPORT_PERMISSION, DeIdFormExportListView.page_title,
        lambda domain: domain_has_privilege(domain, privileges.DEIDENTIFIED_DATA))
    yield ReportPermission(
        CASE_EXPORT_PERMISSION, CaseExportListView.page_title, lambda domain: True)
    yield ReportPermission(
        SMS_EXPORT_PERMISSION, DownloadNewSmsExportView.page_title, lambda domain: True)


def can_download_data_files(domain):
    return toggles.DATA_FILE_DOWNLOAD.enabled(domain)


def can_view_form_exports(couch_user, domain):
    return couch_user.can_edit_data(domain) or has_permission_to_view_report(
        couch_user, domain, FORM_EXPORT_PERMISSION
    )


def can_view_case_exports(couch_user, domain):
    return couch_user.can_edit_data(domain) or has_permission_to_view_report(
        couch_user, domain, CASE_EXPORT_PERMISSION
    )


def can_view_sms_exports(couch_user, domain):
    return couch_user.can_edit_data(domain) or has_permission_to_view_report(
        couch_user, domain, SMS_EXPORT_PERMISSION
    )


def has_permission_to_view_report(couch_user, domain, report_to_check):
    from corehq.apps.users.decorators import get_permission_name
    from corehq.apps.users.models import Permissions
    return (
        couch_user.can_view_reports(domain) or
        couch_user.has_permission(
            domain,
            get_permission_name(Permissions.view_report),
            data=report_to_check
        )
    )
