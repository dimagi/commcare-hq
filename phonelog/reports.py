import json
import logging
from collections import defaultdict
from django.conf import settings
from django.utils import html
from corehq.apps.reports.datatables.DTSortType import DATE
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DTSortDirection
from corehq.apps.reports.fields import DeviceLogTagField, DeviceLogUsersField, DeviceLogDevicesField
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_noop
from phonelog.models import UserLog, Log

logger = logging.getLogger(__name__)

DATA_NOTICE = ugettext_noop(
        "This report may not always show the latest log data but will "
        "be updated over time")

TAGS = {
    "error": ['exception', 'rms-repair', 'rms-spill'],
    "warning": ['case-recreate', 'permissions_notify', 'time message'],
}

class PhonelogReport(DeploymentsReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    special_notice = DATA_NOTICE



class FormErrorReport(DeploymentsReport, DatespanMixin):
    name = ugettext_noop("Errors & Warnings Summary")
    slug = "form_errors"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    special_notice = DATA_NOTICE
    is_cacheable = False

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Username", span=4),
                                DataTablesColumn("Number of Forms", span=2, sort_type=DTSortType.NUMERIC),
                                DataTablesColumn("Number of Warnings", span=2, sort_type=DTSortType.NUMERIC),
                                DataTablesColumn("Number of Errors", span=2, sort_type=DTSortType.NUMERIC))

    @property
    def rows(self):
#        for user_type in [HQUserType.DEMO_USER, HQUserType.ADMIN]:
#            if self.user_filter[user_type].show\
#            and not HQUserType.human_readable[user_type] in self.usernames:
#                temp_user = TempCommCareUser(self.domain, HQUserType.human_readable[user_type], "unknownID")
#                self._users.append(temp_user)
        rows = []
        query_string = self.request.META['QUERY_STRING']
        child_report_url = DeviceLogDetailsReport.get_url(domain=self.domain)
        for user in self.users:
            # userlogs = UserLog.objects.filter(username__exact=user.get('raw_username')).values('xform_id')
            # xform_ids = [u["xform_id"] for u in userlogs]
            phonelogs = Log.objects.filter(username__exact=user.get('raw_username'),
                date__range=[self.datespan.startdate_param_utc, self.datespan.enddate_param_utc])
            error_count = len(phonelogs.filter(type__in=TAGS["error"]))
            warning_count = len(phonelogs.filter(type__in=TAGS["warning"]))

            formatted_warning_count = '<span class="label label-warning">%d</span>' % warning_count if warning_count > 0\
                                        else '<span class="label">%d</span>' % warning_count
            formatted_error_count = '<span class="label label-important">%d</span>' % error_count if error_count > 0\
                                        else '<span class="label">%d</span>' % error_count

            from corehq.apps.reports.util import make_form_couch_key
            key = make_form_couch_key(self.domain, user_id=user.get('user_id'))
            data = get_db().view("reports_forms/all_forms",
                startkey=key + [self.datespan.startdate_param_utc],
                endkey=key + [self.datespan.enddate_param_utc, {}],
                reduce=True,
                stale=settings.COUCH_STALE_QUERY,
            ).all()
            form_count = data[0]['value'] if data else 0
            username_formatted = '<a href="%(url)s?%(query_string)s%(error_slug)s=True&%(username_slug)s=%(raw_username)s">%(username)s</a>' % {
                "url": child_report_url,
                "error_slug": DeviceLogTagField.errors_only_slug,
                "username_slug": DeviceLogUsersField.slug,
                "username": user.get('username_in_report'),
                "raw_username": user.get('raw_username'),
                "query_string": "%s&" % query_string if query_string else ""
            }
            rows.append([self.table_cell(user.get('raw_username'), username_formatted),
                         self.table_cell(form_count),
                         self.table_cell(warning_count, formatted_warning_count),
                         self.table_cell(error_count, formatted_error_count)])
        return rows

class DeviceLogDetailsReport(PhonelogReport):
    name = ugettext_noop("Device Log Details")
    slug = "log_details"
    fields = ['corehq.apps.reports.fields.DatespanField',
              'corehq.apps.reports.fields.DeviceLogTagField',
              'corehq.apps.reports.fields.DeviceLogUsersField',
              'corehq.apps.reports.fields.DeviceLogDevicesField']
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

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("Date", span=1, sort_type=DATE,
                                                 sort_direction=[DTSortDirection.DSC,DTSortDirection.ASC]),
                                DataTablesColumn("Log Type", span=1),
                                DataTablesColumn("Logged in Username", span=2),
                                DataTablesColumn("Device Users", span=2),
                                DataTablesColumn("Device ID", span=2),
                                DataTablesColumn("Message", span=5),
                                DataTablesColumn("App Version", span=1))

    _errors_only = None
    @property
    def errors_only(self):
        if self._errors_only is None:
            self._errors_only = self.request.GET.get(DeviceLogTagField.errors_only_slug, False)
        return self._errors_only

    _device_log_users = None
    @property
    def device_log_users(self):
        if self._device_log_users is None:
            self._device_log_users = self.request.GET.getlist(DeviceLogUsersField.slug)
        return self._device_log_users

    _selected_tags = None
    @property
    def selected_tags(self):
        if self._selected_tags is None:
            self._selected_tags = self.request.GET.getlist(DeviceLogTagField.slug)
        return self._selected_tags

    _selected_devices = None
    @property
    def selected_devices(self):
        if self._selected_devices is None:
            self._selected_devices = set(self.request.GET.getlist(DeviceLogDevicesField.slug))
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

    @memoized
    def get_device_users(self, log_id):
        return []

    @property
    def rows(self):
        rows = []
        # phonelogs = Log.objects.filter(xform_id__in=xform_ids,
        #         date__range=[self.datespan.startdate_param_utc, self.datespan.enddate_param_utc])
        #     error_count = len(phonelogs.filter(type__in=TAGS["error"]))
        #     warning_count = len(phonelogs.filter(type__in=TAGS["warning"]))

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

    def _create_rows(self, logs, matching_id=None):
        row_set = []
        user_query = self._filter_query_by_slug(DeviceLogUsersField.slug)
        device_query = self._filter_query_by_slug(DeviceLogDevicesField.slug)
        logs = logs.all().order_by('-date')[:self.limit] if matching_id else logs.all().order_by('date')
        for log in logs:
            date = str(log.date)
            date_fmt = tz_utils.string_to_prertty_time(date, self.timezone, fmt="%b %d, %Y %H:%M:%S")

            username = log.username or 'unknown'
            username_fmt = '<a href="%(url)s">%(username)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                        DeviceLogUsersField.slug,
                                        username,
                                        user_query),
                "username": username
            }

            device_users = self.get_device_users(log.id)
            device_users_fmt = ', '.join([ 
                '<a href="%(url)s">%(username)s</a>' % { "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                                                                 DeviceLogUsersField.slug,
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
                                        DeviceLogDevicesField.slug,
                                        device,
                                        device_query),
                "device": device
            }

            version = log.app_version
            ver_format = '%s <a href="#" data-datatable-tooltip="left" data-datatable-tooltip-text="%s"><i class="icon icon-info-sign"></i></a>'\
            % (version.split(' ')[0], html.escape(version))

            row_set.append([self.table_cell(date, date_fmt),
                            self.table_cell(log_tag, log_tag_format),
                            self.table_cell(username, username_fmt),
                            self.table_cell(device_users, device_users_fmt),
                            self.table_cell(device, device_fmt),
                            self.table_cell(log.msg),
                            self.table_cell(version, ver_format)])
        return row_set

    def _filter_query_by_slug(self, slug):
        current_query = self.request.META['QUERY_STRING'].split('&')
        return "&".join([query_item for query_item in current_query if not query_item.startswith(slug)])
