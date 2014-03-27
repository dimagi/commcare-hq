import json
import logging
from collections import defaultdict
from django.conf import settings
from django.db.models import Count
from django.utils import html
from corehq.apps.reports.datatables.DTSortType import DATE
from corehq.apps.reports.filters.devicelog import DeviceLogTagFilter, DeviceLogUsersFilter, DeviceLogDevicesFilter
from corehq.apps.reports.generic import PaginatedReportMixin, GetParamsMixin
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DTSortDirection
from corehq.apps.reports.util import _report_user_dict
from corehq.apps.users.models import CommCareUser
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop
from phonelog.models import Log

logger = logging.getLogger(__name__)

DATA_NOTICE = ugettext_noop(
        "This report may not always show the latest log data but will "
        "be updated over time")

TAGS = {
    "error": ['exception', 'rms-repair', 'rms-spill'],
    "warning": ['case-recreate', 'permissions_notify', 'time message'],
}

class PhonelogReport(GetParamsMixin, DeploymentsReport, DatespanMixin, PaginatedReportMixin):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    special_notice = DATA_NOTICE
    ajax_pagination = True
    total_records = 0



class FormErrorReport(PhonelogReport):
    name = ugettext_noop("Errors & Warnings Summary")
    slug = "form_errors"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    special_notice = DATA_NOTICE
    is_cacheable = False
    default_sort = {'users': 'asc'}

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Username", span=4, prop_name='users'),
                                DataTablesColumn("Number of Warnings", span=2,
                                                 sort_type=DTSortType.NUMERIC, prop_name='warnings'),
                                DataTablesColumn("Number of Errors", span=2,
                                                 sort_type=DTSortType.NUMERIC, prop_name='errors'))

    _all_logs = None
    @property
    def all_logs(self):
        if self._all_logs is None:
            self._all_logs = Log.objects.filter(domain__exact=self.domain,
                date__range=[self.datespan.startdate_param_utc, self.datespan.enddate_param_utc])
        return self._all_logs

    _error_logs = None
    @property
    def error_logs(self):
        if self._error_logs is None:
            self._error_logs = self.all_logs.filter(type__in=TAGS["error"])
        return self._error_logs

    _warning_logs = None
    @property
    def warning_logs(self):
        if self._warning_logs is None:
            self._warning_logs = self.all_logs.filter(type__in=TAGS["warning"])
        return self._warning_logs

    @property
    def users_to_show(self):
        by, direction = self.get_sorting_block()[0].items()[0]
        paged = slice(self.pagination.start, self.pagination.start + self.pagination.count)
        if by == 'users':
            self.total_records = len(self.users)
            return sorted(self.users, reverse=direction=='desc')[paged]
        logs = {"errors": self.error_logs, "warnings": self.warning_logs}[by]
        self.total_records = logs.values('username').annotate(usernames=Count('username')).count()

        if direction == 'desc':
            username_data = logs.values('username').annotate(usernames=Count('username'))\
            .order_by('usernames')[paged]
        else:
            username_data = logs.values('username').annotate(usernames=Count('username'))\
            .order_by('usernames').reverse()[paged]
        usernames = [uc["username"] for uc in username_data]

        def make_user(username):
            user = CommCareUser.get_by_username('%s@%s.commcarehq.org' % (username, self.domain))
            if user:
                return _report_user_dict(user)
            return {"raw_username": username, "username_in_report": username}

        return [make_user(u) for u in usernames]

    @property
    def rows(self):
        rows = []
        query_string = self.request.META['QUERY_STRING']
        child_report_url = DeviceLogDetailsReport.get_url(domain=self.domain)
        for user in self.users_to_show:
            error_count = self.error_logs.filter(username__exact=user.get('raw_username')).count()
            warning_count = self.warning_logs.filter(username__exact=user.get('raw_username')).count()

            formatted_warning_count = '<span class="label label-warning">%d</span>' % warning_count if warning_count > 0\
                                        else '<span class="label">%d</span>' % warning_count
            formatted_error_count = '<span class="label label-important">%d</span>' % error_count if error_count > 0\
                                        else '<span class="label">%d</span>' % error_count

            username_formatted = '<a href="%(url)s?%(query_string)s%(error_slug)s=True&%(username_slug)s=%(raw_username)s">%(username)s</a>' % {
                "url": child_report_url,
                "error_slug": DeviceLogTagFilter.errors_only_slug,
                "username_slug": DeviceLogUsersFilter.slug,
                "username": user.get('username_in_report'),
                "raw_username": user.get('raw_username'),
                "query_string": "%s&" % query_string if query_string else ""
            }
            rows.append([username_formatted, formatted_warning_count, formatted_error_count])
        return rows

class DeviceLogDetailsReport(PhonelogReport):
    name = ugettext_noop("Device Log Details")
    slug = "log_details"
    fields = ['corehq.apps.reports.fields.DatespanField',
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

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Date", span=1, sort_type=DATE, prop_name='date',
                                                 sort_direction=[DTSortDirection.DSC,DTSortDirection.ASC]),
                                DataTablesColumn("Log Type", span=1, prop_name='type'),
                                DataTablesColumn("Logged in Username", span=2, prop_name='username'),
                                DataTablesColumn("Device Users", span=2),
                                DataTablesColumn("Device ID", span=2, prop_name='device_id'),
                                DataTablesColumn("Message", span=5, prop_name='msg'),
                                DataTablesColumn("App Version", span=1, prop_name='app_version'))

    _errors_only = None
    @property
    def errors_only(self):
        if self._errors_only is None:
            self._errors_only = self.request.GET.get(DeviceLogTagFilter.errors_only_slug, False)
        return self._errors_only

    _device_log_users = None
    @property
    def device_log_users(self):
        if self._device_log_users is None:
            self._device_log_users = self.request.GET.getlist(DeviceLogUsersFilter.slug)
        return self._device_log_users

    _selected_tags = None
    @property
    def selected_tags(self):
        if self._selected_tags is None:
            self._selected_tags = self.request.GET.getlist(DeviceLogTagFilter.slug)
        return self._selected_tags

    _selected_devices = None
    @property
    def selected_devices(self):
        if self._selected_devices is None:
            self._selected_devices = set(self.request.GET.getlist(DeviceLogDevicesFilter.slug))
        return self._selected_devices

    _filters = None
    @property
    def filters(self):
        if self._filters is None:
            self._filters = set()
            if self.selected_tags:
                self._filters.add('tag')
            if self.devices:
                self._filters.add('device')
            if self.device_log_users:
                self._filters.add('user')

        return self._filters

    _devices_for_users = None
    @property
    def devices_for_users(self):
        if self._devices_for_users is None:
            device_ids_for_username = defaultdict(set)

            for datum in get_db().view('phonelog/device_log_users',
                                       startkey=[self.domain],
                                       endkey=[self.domain, {}],
                                       group=True,
                                       reduce=True,
                                       stale=settings.COUCH_STALE_QUERY):
                # Begin dependency on particulars of view output
                username = datum['key'][2]
                device_id = datum['key'][1]
                # end dependency
                device_ids_for_username[username].add(device_id)

            self._devices_for_users = set([device_id for user in self.device_log_users
                                                     for device_id in device_ids_for_username[user]])

        return self._devices_for_users

    @property
    def devices(self):
        return self.selected_devices

    _goto_key = None
    @property
    def goto_key(self):
        if self._goto_key is None:
            self._goto_key = self.request_params.get('goto', None)
        return self._goto_key

    _limit = None
    @property
    def limit(self):
        if self._limit is None:
            self._limit = self.request_params.get('limit', 100)
        return self._limit

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
            new_title = "Errors &amp; Warnings Log <small>for %s</small>" % ", ".join(self.device_log_users) \
                if self.device_log_users else "Errors &amp; Warnings Log"
        elif self.goto_key:
            record_desc = '"%s" at %s' % (self.goto_key[2],
                                          tz_utils.string_to_prertty_time(self.goto_key[-1], self.timezone))
            new_title = "Last %s Logs <small>before %s</small>" % (self.limit, record_desc)
        return mark_safe(new_title)

    @property
    def rows(self):
        if self.goto_key:
            log = Log.objects.get(pk=self.goto_key)#.values(["domain", "date"])
            assert log.domain == self.domain
            logs = Log.objects.filter(date__lte=log.date, domain__exact=self.domain,
                                      device_id__exact=log.device_id)
            return self._create_rows(logs, matching_id=log.id)
        else:
            logs = Log.objects.filter(date__range=[self.datespan.startdate_param_utc,
                                                   self.datespan.enddate_param_utc],
                                      domain__exact=self.domain)
            if self.errors_only:
                logs = logs.filter(type__in=TAGS['error']+TAGS['warning'])
            elif 'tag' in self.filters:
                logs = logs.filter(type__in=self._selected_tags)

            if 'user' in self.filters:
                logs = logs.filter(username__in=self.device_log_users)
            if 'device' in self.filters:
                logs = logs.filter(device_id__in=self.devices)
            return self._create_rows(logs)

    @property
    def ordering(self):
        by, direction = self.get_sorting_block()[0].items()[0]
        return '-' + by if direction == 'desc' else by

    def _create_rows(self, logs, matching_id=None):
        row_set = []
        user_query = self._filter_query_by_slug(DeviceLogUsersFilter.slug)
        device_query = self._filter_query_by_slug(DeviceLogDevicesFilter.slug)
        paged = slice(self.pagination.start, self.pagination.start + self.pagination.count + 1)
        self.total_records = logs.count()
        for log in logs.order_by(self.ordering)[paged]:
            date = str(log.date)
            date_fmt = tz_utils.string_to_prertty_time(date, self.timezone, fmt="%b %d, %Y %H:%M:%S")

            username = log.username or 'unknown'
            username_fmt = '<a href="%(url)s">%(username)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                        DeviceLogUsersFilter.slug,
                                        username,
                                        user_query),
                "username": username
            }

            device_users = [u["username"]for u in log.device_users.values('username').all()]
            device_users_fmt = ', '.join([ 
                '<a href="%(url)s">%(username)s</a>' % { "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                                                                 DeviceLogUsersFilter.slug,
                                                                                 username,
                                                                                 user_query),
                                                         "username": username }
                for username in device_users
            ])

            log_tag = log.type or 'unknown'
            tag_classes = ["label"]
            if log_tag in self.tag_labels:
                tag_classes.append(self.tag_labels[log_tag])

            log_tag_format = '<a href="%(url)s" class="%(classes)s"%(extra_params)s data-datatable-tooltip="right" data-datatable-tooltip-text="%(tooltip)s">%(text)s</a>' % {
                "url": "%s?goto=%s" % (self.get_url(domain=self.domain), html.escape(json.dumps(log.id))),
                "classes": " ".join(tag_classes),
                "text": log_tag,
                "extra_params": ' data-datatable-highlight-closest="tr"' if log.id == matching_id else '',
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

            version = log.app_version
            ver_format = '%s <a href="#" data-datatable-tooltip="left" data-datatable-tooltip-text="%s"><i class="icon icon-info-sign"></i></a>'\
            % (version.split(' ')[0], html.escape(version))

            row_set.append([date_fmt,
                            log_tag_format,
                            username_fmt,
                            device_users_fmt,
                            device_fmt,
                            log.msg,
                            ver_format])
        return row_set

    def _filter_query_by_slug(self, slug):
        current_query = self.request.META['QUERY_STRING'].split('&')
        return "&".join([query_item for query_item in current_query if not query_item.startswith(slug)])
