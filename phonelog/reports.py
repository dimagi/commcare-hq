import datetime
import json
import logging
import dateutil
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils import html
import pytz
from corehq.apps.reports import util
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DTSortDirection
from corehq.apps.reports.fields import DeviceLogTagField, DeviceLogUsersField, DeviceLogDevicesField
from corehq.apps.reports.models import HQUserType, TempCommCareUser
from corehq.apps.reports.standard import StandardTabularHQReport, StandardDateHQReport
from dimagi.utils.couch.database import get_db
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request, get_url_base

class FormErrorReport(StandardTabularHQReport, StandardDateHQReport):
    name = "Errors &amp; Warnings Summary"
    slug = "form_errors"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    def get_headers(self):
        return DataTablesHeader(DataTablesColumn("Username", span=4),
                                DataTablesColumn("Number of Forms", span=2, sort_type=DTSortType.NUMERIC),
                                DataTablesColumn("Number of Warnings", span=2, sort_type=DTSortType.NUMERIC),
                                DataTablesColumn("Number of Errors", span=2, sort_type=DTSortType.NUMERIC))

    def get_parameters(self):
        usernames = [user.raw_username for user in self.users]
        # this is really for testing purposes, should probably remove before production
        for user_type in [HQUserType.DEMO_USER, HQUserType.ADMIN]:
            if self.user_filter[user_type].show\
            and not HQUserType.human_readable[user_type] in usernames:
                temp_user = TempCommCareUser(self.domain, HQUserType.human_readable[user_type], "unknownID")
                self.users.append(temp_user)

    def get_rows(self):
        rows = []
        query_string = self.request.META['QUERY_STRING']
        child_report_url = reverse("report_dispatcher", args=[self.domain, DeviceLogDetailsReport.slug])
        for user in self.users:
            key = [self.domain, "errors_only", user.raw_username]
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

            key = [self.domain, user.userID]
            data = get_db().view("reports/submit_history",
                startkey=key + [self.datespan.startdate_param_utc],
                endkey=key + [self.datespan.enddate_param_utc, {}],
                reduce=True
            ).all()
            form_count = data[0]['value'] if data else 0
            username_formatted = '<a href="%(url)s?%(query_string)s%(error_slug)s=True&%(username_slug)s=%(raw_username)s">%(username)s</a>' % {
                "url": child_report_url,
                "error_slug": DeviceLogTagField.errors_only_slug,
                "username_slug": DeviceLogUsersField.slug,
                "username": user.username_in_report,
                "raw_username": user.raw_username,
                "query_string": "%s&" % query_string if query_string else ""
            }
            rows.append([util.format_datatables_data(username_formatted, user.raw_username),
                         util.format_datatables_data(form_count,form_count),
                         util.format_datatables_data(formatted_warning_count, warning_count),
                         util.format_datatables_data(formatted_error_count, error_count)])
        return rows

class DeviceLogDetailsReport(StandardTabularHQReport, StandardDateHQReport):
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


    def get_headers(self):
        return DataTablesHeader(DataTablesColumn("Date", span=1, sort_direction=[DTSortDirection.DSC,DTSortDirection.ASC]),
                                DataTablesColumn("Log Type", span=1),
                                DataTablesColumn("Logged in Username", span=2),
                                DataTablesColumn("Device ID", span=2),
                                DataTablesColumn("Message", span=5),
                                DataTablesColumn("App Version", span=1))

    def get_parameters(self):
        self.errors_only = self.request.GET.get(DeviceLogTagField.errors_only_slug, False)
        self.selected_tags = self.request.GET.getlist(DeviceLogTagField.slug)
        self.usernames = self.request.GET.getlist(DeviceLogUsersField.slug)
        self.devices = self.request.GET.getlist(DeviceLogDevicesField.slug)
        self.goto_key = self.request_params.get('goto', None)
        self.hide_filters = bool(self.goto_key)
        self.limit = self.request_params.get('limit', 100)
        self.this_report_url = reverse("report_dispatcher", args=[self.domain, self.slug])
        breadcrumbs_template = """<li>
    <a href="%(parent_report_url)s">%(parent_report_title)s</a> <span class="divider">&gt;</span>
</li>
<li class="active">
    <div id="report-title"><a href="#">%(report_name)s</a></div>
</li>"""
        if self.errors_only:
            self.custom_breadcrumbs = breadcrumbs_template % {
                "parent_report_url": reverse("report_dispatcher", args=[self.domain, FormErrorReport.slug]),
                "parent_report_title": FormErrorReport.name,
                "report_name": "Errors &amp; Warnings Log <small>for %s</small>" % ", ".join(self.usernames) if self.usernames
                else "Errors &amp; Warnings Log"
            }
        elif self.goto_key:
            record_desc = '"%s" at %s' % (self.goto_key[2], tz_utils.string_to_prertty_time(self.goto_key[-1], self.timezone))
            self.custom_breadcrumbs = breadcrumbs_template % {
                "parent_report_url": self.this_report_url,
                "parent_report_title": self.name,
                "report_name": "Last %s Logs <small>before %s</small>" % (self.limit, record_desc)
            }

    def get_rows(self):
        rows = []
        view = "phonelog/devicelog_data"

        if self.goto_key:
            data = get_db().view(view,
                startkey=[self.domain, "basic", self.goto_key[-1]],
                limit=self.limit,
                reduce=False,
                descending=True
            ).all()
            rows.extend(self.create_rows(data, self.goto_key))
        else:
            if self.errors_only and self.usernames:
                key_set = [[self.domain, "errors_only", username] for username in self.usernames]
            elif self.errors_only:
                key_set = [[self.domain, "all_errors_only"]]
            elif self.selected_tags and self.usernames and self.devices:
                key_set = [[self.domain, "tag_username_device", tag, username, device] for tag in self.selected_tags
                                                                        for username in self.usernames
                                                                        for device in self.devices]
            elif (not self.devices) and self.selected_tags and self.usernames:
                key_set = [[self.domain, "tag_username", tag, username] for tag in self.selected_tags
                                                                        for username in self.usernames]
            elif (not self.usernames) and self.selected_tags and self.devices:
                key_set = [[self.domain, "tag_device", tag, device] for tag in self.selected_tags
                                                                    for device in self.devices]
            elif (not self.selected_tags) and self.usernames and self.devices:
                key_set = [[self.domain, "username_device", username, device] for username in self.usernames
                                                                              for device in self.devices]
            elif (not self.usernames) and (not self.selected_tags) and self.devices:
                key_set = [[self.domain, "device", device] for device in self.devices]
            elif (not self.devices) and (not self.selected_tags) and self.usernames:
                key_set = [[self.domain, "username", username] for username in self.usernames]
            elif (not self.devices) and (not self.usernames) and self.selected_tags:
                key_set = [[self.domain, "tag", tag] for tag in self.selected_tags]
            else:
                key_set = [[self.domain, "basic"]]

            for key in key_set:
                data = get_db().view(view,
                    startkey=key+[self.datespan.startdate_param_utc],
                    endkey=key+[self.datespan.enddate_param_utc, {}],
                    reduce=False
                ).all()
                rows.extend(self.create_rows(data))
        return rows

    def create_rows(self, data, matching_key=None):
        row_set = []
        for item in data:
            entry = item['value']
            date = entry['@date']
            date_fmt = tz_utils.string_to_prertty_time(date, self.timezone)

            username = entry.get('user','unknown')
            username_fmt = '<a href="%(url)s">%(username)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.this_report_url,
                                        DeviceLogUsersField.slug,
                                        username,
                                        self.request.META['QUERY_STRING']),
                "username": username
            }


            log_tag = entry.get('type','unknown')
            tag_classes = ["label"]
            if log_tag in self.tag_labels:
                tag_classes.append(self.tag_labels[log_tag])

            goto_key = [self.domain, "tag_username", log_tag, username, item['key'][-1]]

            log_tag_format = '<a href="%(url)s" class="%(classes)s"%(extra_params)s data-datatable-tooltip="right" data-datatable-tooltip-text="%(tooltip)s">%(text)s</a>' % {
                "url": "%s?goto=%s" % (self.this_report_url, html.escape(json.dumps(goto_key))),
                "classes": " ".join(tag_classes),
                "text": log_tag,
                "extra_params": ' data-datatable-highlight-closest="tr"' if goto_key == matching_key else '',
                "tooltip": "Show the surrounding 100 logs."
            }

            device = entry.get('device_id','')
            device_fmt = '<a href="%(url)s">%(device)s</a>' % {
                "url": "%s?%s=%s&%s" % (self.this_report_url,
                                        DeviceLogDevicesField.slug,
                                        device,
                                        self.request.META['QUERY_STRING']),
                "device": device
            }

            version = entry.get('version', 'unknown')
            ver_format = '%s <a href="#" data-datatable-tooltip="left" data-datatable-tooltip-text="%s"><i class="icon icon-info-sign"></i></a>'\
            % (version.split(' ')[0], html.escape(version))

            row_set.append([util.format_datatables_data(date_fmt, date),
                            util.format_datatables_data(log_tag_format, log_tag),
                            util.format_datatables_data(username_fmt, username),
                            util.format_datatables_data(device_fmt, device),
                            entry.get('msg', ''),
                            util.format_datatables_data(ver_format, version)])
        return row_set