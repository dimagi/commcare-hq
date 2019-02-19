from __future__ import absolute_import
from __future__ import unicode_literals
import json
import logging

from django.conf import settings
from django.db.models import Q
from django.utils import html

from corehq.apps.receiverwrapper.util import (
    get_version_from_appversion_text,
    get_commcare_version_from_appversion_text,
)
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
)
from corehq.util.timezones.conversions import ServerTime
from memoized import memoized
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
from .models import DeviceReportEntry
from .utils import device_users_by_xform
from six.moves.urllib.parse import urlencode
import six

logger = logging.getLogger(__name__)

DATA_NOTICE = ugettext_lazy(
    "This report will only show data for the past 60 days. Furthermore the report may not "
    "always show the latest log data but will be updated over time",
)

TAGS = {
    "error": ['exception', 'rms-repair', 'rms-spill'],
    "warning": ['case-recreate', 'permissions_notify', 'time message'],
}


class BaseDeviceLogReport(GetParamsMixin, DatespanMixin, PaginatedReportMixin):
    name = ugettext_lazy("Device Log Details")
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
    special_notice = DATA_NOTICE
    ajax_pagination = True
    total_records = 0
    default_rows = 100
    default_sort = {'date': 'asc'}
    emailable = True
    exportable = True
    exportable_all = True
    inclusive = False

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(ugettext_lazy("Log Date"), span=1, sort_type=DATE, prop_name='date',
                             sort_direction=[DTSortDirection.DSC,
                                             DTSortDirection.ASC]),
            DataTablesColumn(ugettext_lazy("Log Submission Date"), span=1, sort_type=DATE, prop_name='server_date',
                             sort_direction=[DTSortDirection.DSC,
                                             DTSortDirection.ASC]),
            DataTablesColumn(ugettext_lazy("Log Type"), span=1, prop_name='type'),
            DataTablesColumn(ugettext_lazy("Logged in Username"), span=2,
                             prop_name='username'),
            DataTablesColumn(ugettext_lazy("Device Users"), span=2),
            DataTablesColumn(ugettext_lazy("Device ID"), span=2, prop_name='device_id'),
            DataTablesColumn(ugettext_lazy("Message"), span=5, prop_name='msg'),
            DataTablesColumn(ugettext_lazy("App Version"), span=1, prop_name='app_version'),
            DataTablesColumn(ugettext_lazy("CommCare Version"), span=1, prop_name='commcare_version', sortable=False),
        )

    @property
    @memoized
    def errors_only(self):
        return self.request.GET.get(DeviceLogTagFilter.errors_only_slug, False)

    @property
    @memoized
    def device_log_users(self):
        return set([_f for _f in DeviceLogUsersFilter.get_value(self.request, self.domain) if _f])

    @property
    @memoized
    def selected_tags(self):
        return [_f for _f in self.request.GET.getlist(DeviceLogTagFilter.slug) if _f]

    @property
    @memoized
    def selected_devices(self):
        return set([_f for _f in self.request.GET.getlist(DeviceLogDevicesFilter.slug) if _f])

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
        if self.goto_key:
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
        range = slice(self.pagination.start,
                      self.pagination.start + self.pagination.count + 1)
        if self.goto_key:
            log = self.goto_log
            assert log.domain == self.domain
            logs = DeviceReportEntry.objects.filter(
                date__lte=log.date,
                domain__exact=self.domain,
                device_id__exact=log.device_id,
            )
            return self._create_rows(logs, matching_id=log.id, range=range)
        else:
            logs = self._filter_logs()
            return self._create_rows(logs, range=range)

    @property
    def ordering(self):
        by, direction = list(self.get_sorting_block()[0].items())[0]
        return '-' + by if direction == 'desc' else by

    @property
    def get_all_rows(self):
        logs = self._filter_logs()
        return self._create_rows(logs)

    _username_fmt = '<a href="%(url)s">%(username)s</a>'
    _device_users_fmt = '<a href="%(url)s">%(username)s</a>'
    _device_id_fmt = '<a href="%(url)s">%(device)s</a>'
    _log_tag_fmt = ('<a href="%(url)s" class="%(classes)s"%(extra_params)s '
                    'data-datatable-tooltip="right" '
                    'data-datatable-tooltip-text="%(tooltip)s">%(text)s</a>')

    def _create_row(self, log, matching_id, _device_users_by_xform, user_query, device_query):
        log_date = (ServerTime(log.date)
                    .user_time(self.timezone).ui_string())

        server_date = (ServerTime(log.server_date)
                       .user_time(self.timezone).ui_string())

        username = log.username
        username_fmt = self._username_fmt % {
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
            self._device_users_fmt % {
                "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                        DeviceLogUsersFilter.slug,
                                        device_username,
                                        user_query),
                "username": device_username,
            }
            for device_username in device_users
        ])

        log_tag = log.type or 'unknown'
        tag_classes = ["label"]
        if log_tag in self.tag_labels:
            tag_classes.append(self.tag_labels[log_tag])

        if len(tag_classes) == 1:
            tag_classes.append('label-info')

        log_tag_format = self._log_tag_fmt % {
            "url": "%s?goto=%s" % (self.get_url(domain=self.domain),
                                   html.escape(json.dumps(log.id))),
            "classes": " ".join(tag_classes),
            "text": log_tag,
            "extra_params": (' data-datatable-highlight-closest="tr"'
                             if log.id == matching_id else ''),
            "tooltip": "Show the surrounding 100 logs."
        }

        device = log.device_id
        device_fmt = self._device_id_fmt % {
            "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                    DeviceLogDevicesFilter.slug,
                                    device,
                                    device_query),
            "device": device
        }

        app_version = get_version_from_appversion_text(log.app_version) or "unknown"
        commcare_version = get_commcare_version_from_appversion_text(log.app_version) or "unknown"
        return [log_date, server_date, log_tag_format, username_fmt,
                device_users_fmt, device_fmt, log.msg, app_version, commcare_version]

    def _create_rows(self, logs, matching_id=None, range=None):
        _device_users_by_xform = memoized(device_users_by_xform)
        row_set = []
        user_query = self._filter_query_by_slug(DeviceLogUsersFilter.slug)
        device_query = self._filter_query_by_slug(DeviceLogDevicesFilter.slug)

        self.total_records = logs.count()
        logs = logs.order_by(self.ordering)
        if range:
            logs = logs[range]
        for log in logs:
            row_set.append(self._create_row(log, matching_id, _device_users_by_xform, user_query, device_query))

        return row_set

    def _filter_logs(self):
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
        return logs

    def _filter_query_by_slug(self, slug):
        return urlencode({k: v for (k, v) in six.iteritems(self.request.GET) if not k.startswith(slug)})


class DeviceLogDetailsReport(BaseDeviceLogReport, DeploymentsReport):
    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return settings.SERVER_ENVIRONMENT not in settings.NO_DEVICE_LOG_ENVS
