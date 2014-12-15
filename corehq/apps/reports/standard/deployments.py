# coding=utf-8
from datetime import datetime, timedelta
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from casexml.apps.phone.models import SyncLog
from corehq.apps.receiverwrapper.util import get_meta_appversion_text, get_build_version, \
    BuildVersionSource
from couchdbkit import ResourceNotFound
from corehq.apps.app_manager.models import get_app
from corehq.apps.reports.filters.select import SelectApplicationFilter
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import make_form_couch_key, format_datatables_data
from corehq.apps.users.models import CommCareUser
from corehq.toggles import VIEW_SYNC_HISTORY
from corehq.util.couch import get_document_or_404
from couchforms.models import XFormInstance
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from dimagi.utils.couch.database import iter_docs


class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
    Base class for all deployments reports
    """
   
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        # for commtrack/connect projects - only show if the user can view apps
        if project.commtrack_enabled or project.commconnect_enabled:
            return user and (user.is_superuser or user.has_permission(domain, 'edit_apps'))
        return super(DeploymentsReport, cls).show_in_navigation(domain, project, user)


def _build_html(version, version_source):
    version = version or _("Unknown")

    def fmt(title, extra_class=u'', extra_text=u''):
        return format_html(
            u'<span class="label{extra_class}" title="{title}">'
            u'{extra_text}{version}</span>',
            version=version,
            title=title,
            extra_class=extra_class,
            extra_text=extra_text,
        )
    if version_source == BuildVersionSource.BUILD_ID:
        return fmt(title=_("This was taken from build id"),
                   extra_class=u' label-success')
    elif version_source == BuildVersionSource.APPVERSION_TEXT:
        return fmt(title=_("This was taken from appversion text"))
    elif version_source == BuildVersionSource.XFORM_VERSION:
        return fmt(title=_("This was taken from xform version"),
                   extra_text=u'≥ ')
    elif version_source == BuildVersionSource.NONE:
        return fmt(title=_("Unable to determine the build version"))
    else:
        raise AssertionError('version_source must be '
                             'a BuildVersionSource constant')


class ApplicationStatusReport(DeploymentsReport):
    name = ugettext_noop("Application Status")
    slug = "app_status"
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.select.SelectApplicationFilter']

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Last Submission"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Last Sync"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Application (Deployed Version)"),
                help_text=_("""Displays application version of the last submitted form;
                            The currently deployed version may be different."""))
        )

    @property
    def rows(self):
        rows = []
        selected_app = self.request_params.get(SelectApplicationFilter.slug, '')

        for user in self.users:
            last_seen = last_sync = app_name = None

            key = make_form_couch_key(self.domain, user_id=user.user_id,
                                      app_id=selected_app or None)
            xform = XFormInstance.view(
                "reports_forms/all_forms",
                startkey=key+[{}],
                endkey=key,
                include_docs=True,
                descending=True,
                reduce=False,
                limit=1,
            ).first()

            if xform:
                last_seen = xform.received_on
                build_version, build_version_source = get_build_version(xform)

                if xform.app_id:
                    try:
                        app = get_app(self.domain, xform.app_id)
                    except ResourceNotFound:
                        pass
                    else:
                        app_name = app.name
                else:
                    app_name = get_meta_appversion_text(xform)

                build_html = _build_html(build_version, build_version_source)
                app_name = app_name or _("Unknown App")
                app_name = format_html(
                    u'{} {}', app_name, mark_safe(build_html),
                )

            if app_name is None and selected_app:
                continue

            last_sync_log = SyncLog.last_for_user(user.user_id)
            if last_sync_log:
                last_sync = last_sync_log.date

            rows.append(
                [user.username_in_report, _fmt_date(last_seen), _fmt_date(last_sync), app_name or "---"]
            )
        return rows


class SyncHistoryReport(DeploymentsReport):
    name = ugettext_noop("User Sync History")
    slug = "sync_history"
    fields = ['corehq.apps.reports.filters.users.SelectMobileWorkerFilter']

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return (
            user
            and VIEW_SYNC_HISTORY.enabled(user.username)
            and super(DeploymentsReport, cls).show_in_navigation(domain, project, user)
        )

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Sync Log")),
            DataTablesColumn(_("Sync Date"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# of Cases"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Sync Duration"), sort_type=DTSortType.NUMERIC),
        )
        headers.custom_sort = [[1, 'desc']]
        return headers

    @property
    def rows(self):
        user_id = self.request.GET.get('individual')
        if not user_id:
            return []

        # security check
        get_document_or_404(CommCareUser, self.domain, user_id)

        sync_log_ids = [row['id'] for row in SyncLog.view(
            "phone/sync_logs_by_user",
            startkey=[user_id, {}],
            endkey=[user_id],
            descending=True,
            reduce=False,
            limit=10
        )]

        def _sync_log_to_row(sync_log):
            def _fmt_duration(duration):
                if isinstance(duration, int):
                    return format_datatables_data(
                        '<span class="{cls}">{text}</span>'.format(
                            cls=_bootstrap_class(duration or 0, 20, 60),
                            text=_('{} seconds').format(duration),
                        ),
                        duration
                    )
                else:
                    return format_datatables_data(
                        '<span class="label">{text}</span>'.format(
                            text=_("Unknown"),
                        ),
                        -1,
                    )

            def _fmt_id(sync_log_id):
                return '<a href="/search/?q={id}" target="_blank">{id:.5}...</a>'.format(
                    id=sync_log_id
                )

            num_cases = len(sync_log.cases_on_phone)
            return [
                _fmt_id(sync_log.get_id),
                _fmt_date(sync_log.date),
                format_datatables_data(num_cases, num_cases),
                _fmt_duration(sync_log.duration),
            ]

        return [
            _sync_log_to_row(SyncLog.wrap(sync_log_json))
            for sync_log_json in iter_docs(SyncLog.get_db(), sync_log_ids)
        ]


def _fmt_date(date):
    def _timedelta_class(delta):
        return _bootstrap_class(delta, timedelta(days=7), timedelta(days=3))

    if not date:
        return format_datatables_data('<span class="label">{0}</span>'.format(_("Never")), -1)
    else:
        return format_datatables_data(
            '<span class="{cls}">{text}</span>'.format(
                cls=_timedelta_class(datetime.utcnow() - date),
                text=naturaltime(date),
            ),
            date.toordinal(),
        )


def _bootstrap_class(obj, severe, warn):
    """
    gets a bootstrap class for an object comparing to thresholds.
    assumes bigger is worse and default is good.
    """
    if obj > severe:
        return "label label-important"
    elif obj > warn:
        return "label label-warning"
    else:
        return "label label-success"
