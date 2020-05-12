from collections import namedtuple

from django.utils.translation import ugettext_noop

from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege

FORM_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.ExcelExportReport'
DEID_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.DeidExportReport'
CASE_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.CaseExportReport'
ODATA_FEED_PERMISSION = 'corehq.apps.reports.standard.export.ODataFeedListView'
SMS_EXPORT_PERMISSION = 'corehq.apps.reports.standard.export.SMSExportReport'

EXPORT_PERMISSIONS = {
    FORM_EXPORT_PERMISSION,
    DEID_EXPORT_PERMISSION,
    CASE_EXPORT_PERMISSION,
    ODATA_FEED_PERMISSION,
}

ReportPermission = namedtuple('ReportPermission', ['slug', 'title', 'is_visible'])


def get_extra_permissions():
    from corehq.apps.export.views.list import (
        FormExportListView,
        CaseExportListView,
        ODataFeedListView,
    )
    from corehq.apps.export.views.download import DownloadNewSmsExportView
    yield ReportPermission(
        FORM_EXPORT_PERMISSION, FormExportListView.page_title, lambda domain: True)
    yield ReportPermission(
        DEID_EXPORT_PERMISSION, ugettext_noop("Export De-Identified Data"),
        lambda domain: domain_has_privilege(domain, privileges.DEIDENTIFIED_DATA))
    yield ReportPermission(
        CASE_EXPORT_PERMISSION, CaseExportListView.page_title, lambda domain: True)
    yield ReportPermission(
        SMS_EXPORT_PERMISSION, DownloadNewSmsExportView.page_title, lambda domain: True)
    yield ReportPermission(
        ODATA_FEED_PERMISSION, ODataFeedListView.page_title,
        lambda domain: domain_has_privilege(domain, privileges.ODATA_FEED)
    )


def can_download_data_files(domain, couch_user):
    return _has_data_file_permission(domain, couch_user, read_only=True)


def can_upload_data_files(domain, couch_user):
    return _has_data_file_permission(domain, couch_user, read_only=False)


def _has_data_file_permission(domain, couch_user, read_only=True):
    from corehq.apps.users.models import DomainMembershipError
    try:
        role = couch_user.get_role(domain)
    except DomainMembershipError:
        return False

    if not (role and toggles.DATA_FILE_DOWNLOAD.enabled(domain)):
        return False

    return role.permissions.edit_file_dropzone or (read_only and role.permissions.view_file_dropzone)


def can_view_sms_exports(couch_user, domain):
    return has_permission_to_view_report(
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


def can_manage_releases(couch_user, domain, app_id):
    if _can_manage_releases_for_all_apps(couch_user, domain):
        return True
    role = couch_user.get_role(domain)
    return app_id in role.permissions.manage_releases_list


def _can_manage_releases_for_all_apps(couch_user, domain):
    from corehq.apps.users.decorators import get_permission_name
    from corehq.apps.users.models import Permissions
    restricted_app_release = toggles.RESTRICT_APP_RELEASE.enabled(domain)
    if not restricted_app_release:
        return True
    return couch_user.has_permission(
        domain, get_permission_name(Permissions.manage_releases),
        restrict_global_admin=True
    )
