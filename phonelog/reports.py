import datetime
import json
import logging
import dateutil
from collections import defaultdict
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils import html
import pytz
from corehq.apps.reports import util
from corehq.apps.reports.standard import DatespanMixin
from corehq.apps.reports.standard.deployments import DeploymentsReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DTSortDirection
from corehq.apps.reports.fields import DeviceLogTagField, DeviceLogUsersField, DeviceLogDevicesField
from corehq.apps.reports.models import HQUserType, TempCommCareUser
from dimagi.utils.couch.database import get_db
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request, get_url_base

class PhonelogReport(DeploymentsReport, DatespanMixin):
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']


class FormErrorReport(DeploymentsReport, DatespanMixin):
    name = "Errors & Warnings Summary"
    slug = "form_errors"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

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
            key = [self.domain, "errors_only", user.get('raw_username')]
            data = get_db().view("phonelog/devicelog_data",
                    reduce=True,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc]
                ).first()
            warning_count = 0
            error_count = 0
            if data:
                data = data.get('value', {})
                error_count = data.get('errors', 0)
                warning_count = data.get('warnings', 0)

            formatted_warning_count = '<span class="label label-warning">%d</span>' % warning_count if warning_count > 0\
                                        else '<span class="label">%d</span>' % warning_count
            formatted_error_count = '<span class="label label-important">%d</span>' % error_count if error_count > 0\
                                        else '<span class="label">%d</span>' % error_count

            from corehq.apps.reports.util import make_form_couch_key
            key = make_form_couch_key(self.domain, user_id=user.get('user_id'))
            data = get_db().view("reports_forms/all_forms",
                startkey=key + [self.datespan.startdate_param_utc],
                endkey=key + [self.datespan.enddate_param_utc, {}],
                reduce=True
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
    name = "Device Log Details"
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
        return DataTablesHeader(DataTablesColumn("Date", span=1, sort_direction=[DTSortDirection.DSC,DTSortDirection.ASC]),
                                DataTablesColumn("Log Type", span=1),
                                DataTablesColumn("Logged in Username", span=2),
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
            self._selected_devices = self.request.GET.getlist(DeviceLogDevicesField.slug)
        return self._selected_devices

    _devices_for_users = None
    @property
    def devices_for_users(self):
        if self._devices_for_users is None:
            device_ids_for_username = defaultdict(lambda: [])

            for __, device_id, username in get_db().view('phonelog/device_log_users',
                                                         startkey=[self.domain],
                                                         endkey=[self.domain, {}],
                                                         reduce=False):
                device_ids_for_username[username].append(device_id)

            _devices_for_users = [device_id for user in self.device_log_users
                                            for device_id in device_ids_for_username[user]]
            
        return _devices_for_users

    @property
    def devices(self):
        return self.devices_for_users + self.selected_devices

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
        return new_title

#    def get_parameters(self):
#        self.hide_filters = bool(self.goto_key)

    @property
    def rows(self):
        rows = []
        view = "phonelog/devicelog_data"

        if self.goto_key:
            data = get_db().view(view,
                startkey=[self.domain, "basic", self.goto_key[-1]],
                limit=self.limit,
                reduce=False,
                descending=True
            ).all()
            rows.extend(self._create_rows(data, self.goto_key))
        else:
            if self.errors_only:
                key_set = [[self.domain, "all_errors_only"]]
            elif self.selected_tags and self.devices:
                key_set = [[self.domain, "tag_device", tag, device] for tag in self.selected_tags
                                                                    for device in self.devices]
            elif (not self.selected_tags) and self.devices:
                key_set = [[self.domain, "device", device] for device in self.devices]
            elif (not self.devices) and (not self.device_log_users) and self.selected_tags:
                key_set = [[self.domain, "tag", tag] for tag in self.selected_tags]
            else:
                key_set = [[self.domain, "basic"]]

            for key in key_set:
                data = get_db().view(view,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc, {}],
                    reduce=False
                ).all()
                rows.extend(self._create_rows(data))
        return rows

    def _create_rows(self, data, matching_key=None):
        row_set = []
        user_query = self._filter_query_by_slug(DeviceLogUsersField.slug)
        device_query = self._filter_query_by_slug(DeviceLogDevicesField.slug)
        for item in data:
            entry = item['value']
            date = entry['@date']
            date_fmt = tz_utils.string_to_prertty_time(date, self.timezone)

            username = entry.get('user','unknown')
            username_fmt = '<a href="%(url)s">%(username)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                        DeviceLogUsersField.slug,
                                        username,
                                        user_query),
                "username": username
            }

            device_users = entry.get('device_users', [])
            device_users_fmt = ', '.join([ 
                '<a href="%(url)s">%(username)s</a>' % { "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                                                                 DeviceLogUsersField.slug,
                                                                                 username,
                                                                                 user_query),
                                                         "username": username }
                for username in device_users
            ])

            log_tag = entry.get('type','unknown')
            tag_classes = ["label"]
            if log_tag in self.tag_labels:
                tag_classes.append(self.tag_labels[log_tag])

            goto_key = [self.domain, "tag_username", log_tag, username, item['key'][-1]]

            log_tag_format = '<a href="%(url)s" class="%(classes)s"%(extra_params)s data-datatable-tooltip="right" data-datatable-tooltip-text="%(tooltip)s">%(text)s</a>' % {
                "url": "%s?goto=%s" % (self.get_url(domain=self.domain), html.escape(json.dumps(goto_key))),
                "classes": " ".join(tag_classes),
                "text": log_tag,
                "extra_params": ' data-datatable-highlight-closest="tr"' if goto_key == matching_key else '',
                "tooltip": "Show the surrounding 100 logs."
            }

            device = entry.get('device_id','')
            device_fmt = '<a href="%(url)s">%(device)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.get_url(domain=self.domain),
                                        DeviceLogDevicesField.slug,
                                        device,
                                        device_query),
                "device": device
            }

            version = entry.get('version', 'unknown')
            ver_format = '%s <a href="#" data-datatable-tooltip="left" data-datatable-tooltip-text="%s"><i class="icon icon-info-sign"></i></a>'\
            % (version.split(' ')[0], html.escape(version))

            row_set.append([self.table_cell(date, date_fmt),
                            self.table_cell(log_tag, log_tag_format),
                            self.table_cell(username, username_fmt),
                            self.table_cell(device_users, device_users_fmt),
                            self.table_cell(device, device_fmt),
                            self.table_cell(entry.get('msg', '')),
                            self.table_cell(version, ver_format)])
        return row_set

    def _filter_query_by_slug(self, slug):
        current_query = self.request.META['QUERY_STRING'].split('&')
        return "&".join([query_item for query_item in current_query if not query_item.startswith(slug)])
