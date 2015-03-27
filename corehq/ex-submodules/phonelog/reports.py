import json
import logging
from django.db.models import Count, Q
from django.utils import html
from corehq.apps.reports.datatables.DTSortType import DATE
from corehq.apps.reports.filters.devicelog import (
    DeviceLogDevicesFilter,
    DeviceLogTagFilter,
    DeviceLogUsersFilter,
)
from corehq.apps.reports.generic import PaginatedReportMixin, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.datatables import (
    DataTablesColumn,
    DataTablesHeader,
    DTSortDirection,
    DTSortType,
)
from corehq.apps.reports.util import _report_user_dict, SimplifiedUserInfo
from corehq.apps.users.models import CommCareUser
from corehq.util.timezones.conversions import ServerTime
from dimagi.utils.decorators.memoized import memoized
from corehq.util.timezones import utils as tz_utils
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop
from .models import DeviceReportEntry
from .utils import device_users_by_xform

logger = logging.getLogger(__name__)

DATA_NOTICE = ugettext_noop(
    "This report may not always show the latest log data but will "
    "be updated over time",
)

TAGS = {
    "error": ['exception', 'rms-repair', 'rms-spill'],
    "warning": ['case-recreate', 'permissions_notify', 'time message'],
}


class PhonelogReport(GetParamsMixin, DeploymentsReport, DatespanMixin,
                     PaginatedReportMixin):
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    special_notice = DATA_NOTICE
    ajax_pagination = True
    total_records = 0


class FormErrorReport(PhonelogReport):
    name = ugettext_noop("Errors & Warnings Summary")
    slug = "form_errors"
    fields = ['corehq.apps.reports.filters.users.UserTypeFilter',
              'corehq.apps.reports.filters.select.GroupFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    special_notice = DATA_NOTICE
    is_cacheable = False
    default_sort = {'users': 'asc'}

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Username", span=4, prop_name='users'),
            DataTablesColumn("Number of Warnings", span=2,
                             sort_type=DTSortType.NUMERIC,
                             prop_name='warnings'),
            DataTablesColumn("Number of Errors", span=2,
                             sort_type=DTSortType.NUMERIC, prop_name='errors')
        )

    @property
    @memoized
    def all_logs(self):
        return DeviceReportEntry.objects.filter(
            domain__exact=self.domain,
            date__range=[self.datespan.startdate_param_utc,
                         self.datespan.enddate_param_utc],
        )

    @property
    @memoized
    def error_logs(self):
        return self.all_logs.filter(type__in=TAGS["error"])

    @property
    @memoized
    def warning_logs(self):
        return self.all_logs.filter(type__in=TAGS["warning"])

    @property
    def users_to_show(self):
        by, direction = self.get_sorting_block()[0].items()[0]
        paged = slice(self.pagination.start,
                      self.pagination.start + self.pagination.count)
        if by == 'users':
            self.total_records = len(self.users)
            return sorted(self.users, reverse=direction == 'desc')[paged]
        logs = {"errors": self.error_logs, "warnings": self.warning_logs}[by]
        self.total_records = logs.values('username').annotate(
            usernames=Count('username')).count()

        if direction == 'desc':
            username_data = logs.values('username').annotate(
                usernames=Count('username')).order_by('usernames')[paged]
        else:
            username_data = logs.values('username').annotate(
                usernames=Count('username')).order_by('-usernames')[paged]
        usernames = [uc["username"] for uc in username_data]

        def make_user(username):
            user = CommCareUser.get_by_username(
                '%s@%s.commcarehq.org' % (username, self.domain))
            if user:
                return _report_user_dict(user)
            return SimplifiedUserInfo(
                raw_username=username,
                username_in_report=username,
                user_id=None,
                is_active=None,
            )

        return [make_user(u) for u in usernames]

    @property
    def rows(self):
        rows = []
        query_string = self.request.META['QUERY_STRING']
        child_report_url = DeviceLogDetailsReport.get_url(domain=self.domain)
        for user in self.users_to_show:
            error_count = self.error_logs.filter(
                username__exact=user.raw_username).count()
            warning_count = self.warning_logs.filter(
                username__exact=user.raw_username).count()

            formatted_warning_count = (
                '<span class="label label-warning">%d</span>' % warning_count
                if warning_count > 0
                else '<span class="label">%d</span>' % warning_count
            )
            formatted_error_count = (
                '<span class="label label-important">%d</span>' % error_count
                if error_count > 0
                else '<span class="label">%d</span>' % error_count
            )

            username_formatted = (
                '<a href="%(url)s?%(query_string)s%(error_slug)s=True'
                '&%(username_slug)s=%(raw_username)s">%(username)s</a>'
            ) % {
                "url": child_report_url,
                "error_slug": DeviceLogTagFilter.errors_only_slug,
                "username_slug": DeviceLogUsersFilter.slug,
                "username": user.username_in_report,
                "raw_username": user.raw_username,
                "query_string": "%s&" % query_string if query_string else ""
            }
            rows.append([username_formatted, formatted_warning_count,
                         formatted_error_count])
        return rows


class DeviceLogDetailsReport(PhonelogReport):
    name = ugettext_noop("Device Log Details")
    slug = "log_details"
    fields = ['corehq.apps.reports.filters.dates.DatespanFilter',
              'corehq.apps.reports.filters.devicelog.DeviceLogTagFilter',
              'corehq.apps.reports.filters.devicelog.DeviceLogUsersFilter',
              'corehq.apps.reports.filters.devicelog.DeviceLogDevicesFilter']
    tag_labels = {
        "exception": "label-important",
        "rms-repair": "label-important",
        "rms-spill": "label-important",
        "case-recreate": "label-warning",
        "permissions_notify": "label-warning",
        "time message": "label-warning",
        "send-all": "label-info",
    }
    default_rows = 100
    default_sort = {'date': 'asc'}
    inclusive = False

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn("Date", span=1, sort_type=DATE, prop_name='date',
                             sort_direction=[DTSortDirection.DSC,
                                             DTSortDirection.ASC]),
            DataTablesColumn("Log Type", span=1, prop_name='type'),
            DataTablesColumn("Logged in Username", span=2,
                             prop_name='username'),
            DataTablesColumn("Device Users", span=2),
            DataTablesColumn("Device ID", span=2, prop_name='device_id'),
            DataTablesColumn("Message", span=5, prop_name='msg'),
            DataTablesColumn("App Version", span=1, prop_name='app_version'),
        )

    @property
    @memoized
    def errors_only(self):
        return self.request.GET.get(DeviceLogTagFilter.errors_only_slug, False)

    @property
    @memoized
    def device_log_users(self):
        return DeviceLogUsersFilter.get_selected(self.request)

    @property
    @memoized
    def selected_tags(self):
        return self.request.GET.getlist(DeviceLogTagFilter.slug)

    @property
    @memoized
    def selected_devices(self):
        return set(self.request.GET.getlist(DeviceLogDevicesFilter.slug))

    @property
    @memoized
    def filters(self):
        filters = set()
        if self.selected_tags:
            filters.add('tag')
        if self.selected_devices:
            filters.add('device')
        if self.device_log_users:
            filters.add('user')

        return filters

    @property
    @memoized
    def goto_key(self):
        return self.request_params.get('goto', None)

    @property
    @memoized
    def limit(self):
        return self.request_params.get('limit', 100)

    @property
    @memoized
    def goto_log(self):
        if self.goto_key:
            return DeviceReportEntry.objects.get(pk=self.goto_key)

    @property
    def breadcrumbs(self):
        breadcrumbs = None
        if self.errors_only:
            breadcrumbs = dict(
                title=FormErrorReport.name,
                link=FormErrorReport.get_url(domain=self.domain)
            )
        elif self.goto_key:
            breadcrumbs = dict(
                title=self.name,
                link=self.get_url(domain=self.domain)
            )
        return breadcrumbs

    @property
    @memoized
    def rendered_report_title(self):
        new_title = self.name
        if self.errors_only:
            new_title = (
                "Errors &amp; Warnings Log <small>for %s</small>" % (
                    ", ".join(self.device_log_users)
                )
                if self.device_log_users
                else "Errors &amp; Warnings Log"
            )
        elif self.goto_key:
            log = self.goto_log
            new_title = "Last %s Logs <small>before %s</small>" % (
                self.limit,
                ServerTime(log.date).user_time(self.timezone).ui_string()
            )
        return mark_safe(new_title)

    @property
    def rows(self):
        if self.goto_key:
            log = self.goto_log
            assert log.domain == self.domain
            logs = DeviceReportEntry.objects.filter(
                date__lte=log.date,
                domain__exact=self.domain,
                device_id__exact=log.device_id,
            )
            return self._create_rows(logs, matching_id=log.id)
        else:
            logs = DeviceReportEntry.objects.filter(
                date__range=[self.datespan.startdate_param_utc,
                             self.datespan.enddate_param_utc],
                domain__exact=self.domain,
            )
            if self.errors_only:
                logs = logs.filter(type__in=TAGS['error'] + TAGS['warning'])
            elif 'tag' in self.filters:
                logs = logs.filter(type__in=self.selected_tags)

            if 'user' in self.filters:
                user_q = Q(username__in=self.device_log_users)
                if None in self.device_log_users:
                    user_q |= Q(username=None)
                logs = logs.filter(user_q)
            if 'device' in self.filters:
                logs = logs.filter(device_id__in=self.selected_devices)
            return self._create_rows(logs)

    @property
    def ordering(self):
        by, direction = self.get_sorting_block()[0].items()[0]
        return '-' + by if direction == 'desc' else by

    def _create_rows(self, logs, matching_id=None):
        _device_users_by_xform = memoized(device_users_by_xform)
        row_set = []
        user_query = self._filter_query_by_slug(DeviceLogUsersFilter.slug)
        device_query = self._filter_query_by_slug(DeviceLogDevicesFilter.slug)
        paged = slice(self.pagination.start,
                      self.pagination.start + self.pagination.count + 1)

        self.total_records = logs.count()
        for log in logs.order_by(self.ordering)[paged]:
            ui_date = (ServerTime(log.date)
                        .user_time(self.timezone).ui_string())

            username = log.username
            username_fmt = '<a href="%(url)s">%(username)s</a>' % {
                "url": "%s?%s=%s&%s" % (
                    self.get_url(domain=self.domain),
                    DeviceLogUsersFilter.slug,
                    DeviceLogUsersFilter.value_to_param(username),
                    user_query,
                ),
                "username": (
                    username if username
                    else '<span class="label label-info">Unknown</span>'
                )
            }

            device_users = _device_users_by_xform(log.xform_id)
            device_users_fmt = ', '.join([
                '<a href="%(url)s">%(username)s</a>' % {
                    "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                            DeviceLogUsersFilter.slug,
                                            username,
                                            user_query),
                    "username": username,
                }
                for username in device_users
            ])

            log_tag = log.type or 'unknown'
            tag_classes = ["label"]
            if log_tag in self.tag_labels:
                tag_classes.append(self.tag_labels[log_tag])

            log_tag_format = (
                '<a href="%(url)s" class="%(classes)s"%(extra_params)s '
                'data-datatable-tooltip="right" '
                'data-datatable-tooltip-text="%(tooltip)s">%(text)s</a>'
            ) % {
                "url": "%s?goto=%s" % (self.get_url(domain=self.domain),
                                       html.escape(json.dumps(log.id))),
                "classes": " ".join(tag_classes),
                "text": log_tag,
                "extra_params": (' data-datatable-highlight-closest="tr"'
                                 if log.id == matching_id else ''),
                "tooltip": "Show the surrounding 100 logs."
            }

            device = log.device_id
            device_fmt = '<a href="%(url)s">%(device)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                        DeviceLogDevicesFilter.slug,
                                        device,
                                        device_query),
                "device": device
            }

            version = log.app_version or "unknown"
            ver_format = (
                '%s <a href="#" data-datatable-tooltip="left" '
                'data-datatable-tooltip-text="%s">'
                '<i class="icon icon-info-sign"></i></a>'
            ) % (version.split(' ')[0], html.escape(version))

            row_set.append([ui_date, log_tag_format, username_fmt,
                            device_users_fmt, device_fmt, log.msg, ver_format])
        return row_set

    def _filter_query_by_slug(self, slug):
        current_query = self.request.META['QUERY_STRING'].split('&')
        return "&".join([query_item for query_item in current_query
                         if not query_item.startswith(slug)])
