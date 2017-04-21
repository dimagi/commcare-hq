# coding=utf-8
from datetime import date, datetime, timedelta

from django.contrib.humanize.templatetags.humanize import naturaltime
from django.urls import reverse
from django.utils.translation import ugettext_noop, ugettext as _

from casexml.apps.phone.analytics import get_sync_logs_for_user
from casexml.apps.phone.models import SyncLog, SyncLogAssertionError
from couchdbkit import ResourceNotFound
from couchexport.export import SCALAR_NEVER_WAS

from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter, LocationRestrictedMobileWorkerFilter
from dimagi.utils.dates import safe_strftime
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import string_to_utc_datetime
from phonelog.models import UserErrorEntry

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app, get_brief_apps_in_domain
from corehq.apps.es import UserES
from corehq.apps.receiverwrapper.util import get_meta_appversion_text, BuildVersionSource, get_app_version_info, \
    get_version_from_build_id, AppVersionInfo
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import user_display_string
from corehq.const import USER_DATE_FORMAT
from corehq.util.couch import get_document_or_404

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.analytics.esaccessors import (
    get_last_form_submissions_by_user,
    get_all_user_ids_submitted,
)
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.filters.select import SelectApplicationFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.util import format_datatables_data, numcell


class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
    Base class for all deployments reports
    """


@location_safe
class ApplicationStatusReport(DeploymentsReport):
    name = ugettext_noop("Application Status")
    slug = "app_status"
    emailable = True
    exportable = True
    fields = [
        'corehq.apps.reports.filters.users.LocationRestrictedMobileWorkerFilter',
        'corehq.apps.reports.filters.select.SelectApplicationFilter'
    ]

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Last Submission"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Last Sync"),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Application"),
                             help_text=_("Displays application of last submitted form")),
            DataTablesColumn(_("Application Version"),
                             help_text=_("""Displays application version of the last submitted form;
                                         The currently deployed version may be different."""),
                             sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("CommCare Version"),
                             help_text=_("""Displays CommCare version the user last submitted with;
                                         The currently deployed version may be different."""),
                             sort_type=DTSortType.NUMERIC),
        )
        headers.custom_sort = [[1, 'desc']]
        return headers

    @property
    @memoized
    def selected_app_id(self):
        return self.request_params.get(SelectApplicationFilter.slug, None)

    @property
    @memoized
    def users(self):
        mobile_user_and_group_slugs = self.request.GET.getlist(LocationRestrictedMobileWorkerFilter.slug)

        limit_user_ids = []
        if self.selected_app_id:
            limit_user_ids = get_all_user_ids_submitted(self.domain, self.selected_app_id)

        users_data = ExpandedMobileWorkerFilter.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
            include_inactive=False,
            limit_user_ids=limit_user_ids,
        )
        return users_data.combined_users

    @property
    def rows(self):
        rows = []

        user_ids = map(lambda user: user.user_id, self.users)
        user_xform_dicts_map = get_last_form_submissions_by_user(self.domain, user_ids, self.selected_app_id)

        for user in self.users:
            xform_dict = last_seen = last_sync = app_name = None
            app_version_info_from_form = app_version_info_from_sync = None
            if user_xform_dicts_map.get(user.user_id):
                xform_dict = user_xform_dicts_map[user.user_id][0]

            if xform_dict:
                last_seen = string_to_utc_datetime(xform_dict.get('received_on'))

                if xform_dict.get('app_id'):
                    try:
                        app = get_app(self.domain, xform_dict.get('app_id'))
                    except ResourceNotFound:
                        pass
                    else:
                        app_name = app.name
                else:
                    app_name = get_meta_appversion_text(xform_dict['form']['meta'])

                app_version_info_from_form = get_app_version_info(
                    self.domain,
                    xform_dict.get('build_id'),
                    xform_dict.get('version'),
                    xform_dict['form']['meta'],
                )

            if app_name is None and self.selected_app_id:
                continue

            last_sync_log = SyncLog.last_for_user(user.user_id)
            if last_sync_log:
                last_sync = last_sync_log.date
                if last_sync_log.build_id:
                    build_version = get_version_from_build_id(self.domain, last_sync_log.build_id)
                    app_version_info_from_sync = AppVersionInfo(
                        build_version,
                        app_version_info_from_form.commcare_version if app_version_info_from_form else None,
                        BuildVersionSource.BUILD_ID
                    )

            app_version_info_to_use = _choose_latest_version(
                app_version_info_from_sync, app_version_info_from_form,
            )

            commcare_version = _get_commcare_version(app_version_info_to_use)
            build_version = _get_build_version(app_version_info_to_use)

            rows.append([
                user.username_in_report, _fmt_date(last_seen), _fmt_date(last_sync),
                app_name or "---", build_version, commcare_version
            ])
        return rows

    @property
    def export_table(self):
        def _fmt_timestamp(timestamp):
            if timestamp is not None and timestamp >= 0:
                return safe_strftime(date.fromtimestamp(timestamp), USER_DATE_FORMAT)
            return SCALAR_NEVER_WAS

        result = super(ApplicationStatusReport, self).export_table
        table = result[0][1]
        for row in table[1:]:
            # Last submission
            row[1] = _fmt_timestamp(row[1])
            # Last sync
            row[2] = _fmt_timestamp(row[2])
        return result


def _get_commcare_version(app_version_info):
    commcare_version = (_("Unknown CommCare Version"), 0)
    if app_version_info:
        version_text = (
            'CommCare {}'.format(app_version_info.commcare_version)
            if app_version_info.commcare_version
            else _("Unknown CommCare Version")
        )
        commcare_version = (version_text, app_version_info.commcare_version or 0)
    return numcell(commcare_version[0], commcare_version[1], convert="float")


def _get_build_version(app_version_info):
    build_version = (_("Unknown"), 0)
    if app_version_info and app_version_info.build_version:
        build_version = (app_version_info.build_version, app_version_info.build_version)
    return numcell(build_version[0], value=build_version[1])


def _choose_latest_version(*app_versions):
    """
    Chooses the latest version from a list of AppVersion objects - choosing the first one passed
    in with the highest version number.
    """
    usable_versions = filter(None, app_versions)
    if usable_versions:
        return sorted(usable_versions, key=lambda v: v.build_version)[-1]


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
        base_link_url = '{}?id={{id}}'.format(reverse('raw_couch'))

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
            int(date.strftime("%s")),
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


class ApplicationErrorReport(GenericTabularReport, ProjectReport):
    name = ugettext_noop("Application Error Report")
    slug = "application_error"
    ajax_pagination = True
    sortable = False
    fields = ['corehq.apps.reports.filters.select.SelectApplicationFilter']

    # Filter parameters to pull from the URL
    model_fields_to_url_params = [
        ('app_id', SelectApplicationFilter.slug),
        ('version_number', 'version_number'),
    ]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and toggles.APPLICATION_ERROR_REPORT.enabled(user.username)

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(ApplicationErrorReport, self).shared_pagination_GET_params
        shared_params.extend([
            {'name': param, 'value': self.request.GET.get(param, None)}
            for model_field, param in self.model_fields_to_url_params
        ])
        return shared_params

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("User")),
            DataTablesColumn(_("Expression")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Session")),
            DataTablesColumn(_("Application")),
            DataTablesColumn(_("App version")),
            DataTablesColumn(_("Date")),
        )

    @property
    @memoized
    def _queryset(self):
        qs = UserErrorEntry.objects.filter(domain=self.domain)
        for model_field, url_param in self.model_fields_to_url_params:
            value = self.request.GET.get(url_param, None)
            if value:
                qs = qs.filter(**{model_field: value})
        return qs

    @property
    def total_records(self):
        return self._queryset.count()

    @property
    @memoized
    def _apps_by_id(self):
        def link(app):
            return u'<a href="{}">{}</a>'.format(
                reverse('view_app', args=[self.domain, app.get_id]),
                app.name,
            )
        return {
            app.get_id: link(app)
            for app in get_brief_apps_in_domain(self.domain)
        }

    def _ids_to_users(self, user_ids):
        users = (UserES()
                 .domain(self.domain)
                 .user_ids(user_ids)
                 .values('_id', 'username', 'first_name', 'last_name'))
        return {
            u['_id']: user_display_string(u['username'], u['first_name'], u['last_name'])
            for u in users
        }

    @property
    def rows(self):
        start = self.pagination.start
        end = start + self.pagination.count
        errors = self._queryset.order_by('-date')[start:end]
        users = self._ids_to_users({e.user_id for e in errors if e.user_id})
        for error in errors:
            yield [
                users.get(error.user_id, error.user_id),
                error.expr,
                error.msg,
                error.session,
                self._apps_by_id.get(error.app_id, error.app_id),
                error.version_number,
                str(error.date),
            ]
