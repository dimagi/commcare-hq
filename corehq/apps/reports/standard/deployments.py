# coding=utf-8
from datetime import date, datetime, timedelta
from casexml.apps.phone.analytics import get_sync_logs_for_user
from corehq import toggles
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.core.urlresolvers import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from casexml.apps.phone.models import SyncLog, properly_wrap_sync_log, SyncLogAssertionError
from corehq.apps.receiverwrapper.util import get_meta_appversion_text, BuildVersionSource, get_app_version_info
from couchdbkit import ResourceNotFound
from couchexport.export import SCALAR_NEVER_WAS
from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.reports.filters.select import SelectApplicationFilter
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.util import format_datatables_data
from corehq.apps.users.models import CommCareUser
from corehq.const import USER_DATE_FORMAT
from corehq.util.couch import get_document_or_404
from couchforms.analytics import get_last_form_submission_for_user_for_app
from django.utils.translation import ugettext_noop
from django.utils.translation import ugettext as _
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.dates import safe_strftime
from corehq.apps.style.decorators import (
    use_jquery_ui,
    use_bootstrap3,
    use_datatables,
    use_select2,
    use_daterangepicker,
)


class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
    Base class for all deployments reports
    """
    is_bootstrap3 = True

    @use_jquery_ui
    @use_bootstrap3
    @use_datatables
    @use_select2
    @use_daterangepicker
    def set_bootstrap3_status(self, request, *args, **kwargs):
        pass
   
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        # for commtrack projects - only show if the user can view apps
        if project.commtrack_enabled:
            return user and (user.is_superuser or user.has_permission(domain, 'edit_apps'))
        return super(DeploymentsReport, cls).show_in_navigation(domain, project, user)


def _build_html(version_info):
    version = version_info.build_version or _("Unknown")
    def fmt(title, extra_class=u'label-default', extra_text=u''):
        return format_html(
            u'<span class="label{extra_class}" title="{title}">'
            u'{extra_text}{version}</span>',
            version=version,
            title=title,
            extra_class=extra_class,
            extra_text=extra_text,
        )
    if version_info.source == BuildVersionSource.BUILD_ID:
        return fmt(title=_("This was taken from build id"),
                   extra_class=u' label-success')
    elif version_info.source == BuildVersionSource.APPVERSION_TEXT:
        return fmt(title=_("This was taken from appversion text"))
    elif version_info.source == BuildVersionSource.XFORM_VERSION:
        return fmt(title=_("This was taken from xform version"),
                   extra_text=u'≥ ')
    elif version_info.source == BuildVersionSource.NONE:
        return fmt(title=_("Unable to determine the build version"))
    else:
        raise AssertionError('version_source must be '
                             'a BuildVersionSource constant')


class ApplicationStatusReport(DeploymentsReport):
    name = ugettext_noop("Application Status")
    slug = "app_status"
    emailable = True
    exportable = True
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.select.SelectApplicationFilter']

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Last Submission"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Last Sync"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Application (Deployed Version)"),
                help_text=_("""Displays application version of the last submitted form;
                            The currently deployed version may be different."""))
        )
        headers.custom_sort = [[1, 'desc']]
        return headers

    @property
    def rows(self):
        rows = []
        selected_app = self.request_params.get(SelectApplicationFilter.slug, None)

        for user in self.users:
            last_seen = last_sync = app_name = None

            xform = get_last_form_submission_for_user_for_app(
                self.domain, user.user_id, selected_app)

            if xform:
                last_seen = xform.received_on

                if xform.app_id:
                    try:
                        app = get_app(self.domain, xform.app_id)
                    except ResourceNotFound:
                        pass
                    else:
                        app_name = app.name
                else:
                    app_name = get_meta_appversion_text(xform)

                app_version_info = get_app_version_info(xform)
                build_html = _build_html(app_version_info)
                commcare_version = (
                    'CommCare {}'.format(app_version_info.commcare_version)
                    if app_version_info.commcare_version
                    else _("Unknown CommCare Version")
                )
                commcare_version_html = mark_safe('<span class="label label-info">{}</span>'.format(
                    commcare_version)
                )
                app_name = app_name or _("Unknown App")
                app_name = format_html(
                    u'{} {} {}', app_name, mark_safe(build_html), commcare_version_html
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

    @property
    def export_table(self):
        def _fmt_ordinal(ordinal):
            if ordinal is not None and ordinal >= 0:
                return safe_strftime(date.fromordinal(ordinal), USER_DATE_FORMAT)
            return SCALAR_NEVER_WAS

        result = super(ApplicationStatusReport, self).export_table
        table = result[0][1]
        for row in table[1:]:
            # Last submission
            row[1] = _fmt_ordinal(row[1])
            # Last sync
            row[2] = _fmt_ordinal(row[2])
        return result


class SyncHistoryReport(DeploymentsReport):
    DEFAULT_LIMIT = 10
    MAX_LIMIT = 1000
    name = ugettext_noop("User Sync History")
    slug = "sync_history"
    emailable = True
    fields = ['corehq.apps.reports.filters.users.AltPlaceholderMobileWorkerFilter']

    @property
    def report_subtitles(self):
        return [_('Shows the last (up to) {} times a user has synced.').format(self.limit)]

    @property
    def disable_pagination(self):
        return self.limit == self.DEFAULT_LIMIT

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Sync Date"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# of Cases"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Sync Duration"), sort_type=DTSortType.NUMERIC)
        )
        if self.show_extra_columns:
            headers.add_column(DataTablesColumn(_("Sync Log")))
            headers.add_column(DataTablesColumn(_("Sync Log Type")))
            headers.add_column(DataTablesColumn(_("Previous Sync Log")))
            headers.add_column(DataTablesColumn(_("Error Info")))
            headers.add_column(DataTablesColumn(_("State Hash")))
            headers.add_column(DataTablesColumn(_("Last Submitted")))
            headers.add_column(DataTablesColumn(_("Last Cached")))

        headers.custom_sort = [[0, 'desc']]
        return headers

    @property
    def rows(self):
        base_link_url = '{}?q={{id}}'.format(reverse('global_quick_find'))

        user_id = self.request.GET.get('individual')
        if not user_id:
            return []

        # security check
        get_document_or_404(CommCareUser, self.domain, user_id)

        def _sync_log_to_row(sync_log):
            def _fmt_duration(duration):
                if isinstance(duration, int):
                    return format_datatables_data(
                        '<span class="{cls}">{text}</span>'.format(
                            cls=_bootstrap_class(duration or 0, 60, 20),
                            text=_('{} seconds').format(duration),
                        ),
                        duration
                    )
                else:
                    return format_datatables_data(
                        '<span class="label label-default">{text}</span>'.format(
                            text=_("Unknown"),
                        ),
                        -1,
                    )

            def _fmt_id(sync_log_id):
                href = base_link_url.format(id=sync_log_id)
                return '<a href="{href}" target="_blank">{id:.5}...</a>'.format(
                    href=href,
                    id=sync_log_id
                )

            def _fmt_error_info(sync_log):
                if not sync_log.had_state_error:
                    return u'<span class="label label-success">&#10003;</span>'
                else:
                    return (u'<span class="label label-danger">X</span>'
                            u'State error {}<br>Expected hash: {:.10}...').format(
                        _naturaltime_with_hover(sync_log.error_date),
                        sync_log.error_hash,
                    )

            def _get_state_hash_display(sync_log):
                try:
                    return u'{:.10}...'.format(sync_log.get_state_hash())
                except SyncLogAssertionError as e:
                    return _(u'Error computing hash! {}').format(e)


            num_cases = sync_log.case_count()
            columns = [
                _fmt_date(sync_log.date),
                format_datatables_data(num_cases, num_cases),
                _fmt_duration(sync_log.duration),
            ]
            if self.show_extra_columns:
                columns.append(_fmt_id(sync_log.get_id))
                columns.append(sync_log.log_format)
                columns.append(_fmt_id(sync_log.previous_log_id) if sync_log.previous_log_id else '---')
                columns.append(_fmt_error_info(sync_log))
                columns.append(_get_state_hash_display(sync_log))
                columns.append(_naturaltime_with_hover(sync_log.last_submitted))
                columns.append(u'{}<br>{:.10}'.format(_naturaltime_with_hover(sync_log.last_cached),
                                                      sync_log.hash_at_last_cached))

            return columns

        return [_sync_log_to_row(sync_log)
                for sync_log in get_sync_logs_for_user(user_id, self.limit)]

    @property
    def show_extra_columns(self):
        return self.request.user and toggles.SUPPORT.enabled(self.request.user.username)

    @property
    def limit(self):
        try:
            return min(self.MAX_LIMIT, int(self.request.GET.get('limit', self.DEFAULT_LIMIT)))
        except ValueError:
            return self.DEFAULT_LIMIT


def _fmt_date(date):
    def _timedelta_class(delta):
        return _bootstrap_class(delta, timedelta(days=7), timedelta(days=3))

    if not date:
        return format_datatables_data(u'<span class="label label-default">{0}</span>'.format(_("Never")), -1)
    else:
        return format_datatables_data(
            u'<span class="{cls}">{text}</span>'.format(
                cls=_timedelta_class(datetime.utcnow() - date),
                text=_(_naturaltime_with_hover(date)),
            ),
            date.toordinal(),
        )


def _naturaltime_with_hover(date):
    return u'<span title="{}">{}</span>'.format(date, naturaltime(date) or '---')


def _bootstrap_class(obj, severe, warn):
    """
    gets a bootstrap class for an object comparing to thresholds.
    assumes bigger is worse and default is good.
    """
    if obj > severe:
        return "label label-danger"
    elif obj > warn:
        return "label label-warning"
    else:
        return "label label-success"
