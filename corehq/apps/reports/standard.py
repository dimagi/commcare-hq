from _collections import defaultdict
import datetime
import json
import logging
from StringIO import StringIO
import dateutil
from corehq.apps.groups.models import Group
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from django.conf import settings
from django.core.urlresolvers import reverse, NoReverseMatch
from django.http import HttpResponseBadRequest, Http404, HttpResponse
from django.template.defaultfilters import yesno
from django.utils import html
import pytz
from restkit.errors import RequestFailed
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import Application, get_app
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports import util
from corehq.apps.reports.calc import entrytimes
from corehq.apps.reports.custom import HQReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.display import xmlns_to_name, FormType
from corehq.apps.reports.fields import FilterUsersField, CaseTypeField, SelectMobileWorkerField, SelectOpenCloseField, SelectApplicationField
from corehq.apps.reports.models import HQUserType, FormExportSchema
from couchexport.models import SavedExportSchema
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import DatatablesParams, CouchFilter, FilteredPaginator
from dimagi.utils.dates import DateSpan, force_to_datetime
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request, get_url_base

DATE_FORMAT = "%Y-%m-%d"
user_link_template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'

class StandardHQReport(HQReport):
    user_filter = HQUserType.use_defaults()
    fields = ['corehq.apps.reports.fields.FilterUsersField']
    history = None
    use_json = False
    hide_filters = False
    custom_breadcrumbs = None
    base_slug = 'reports'
    asynchronous = True

    def process_basic(self):
        self.request_params = json_request(self.request.GET)
        self.individual = self.request_params.get('individual', '')
        self.user_filter, _ = FilterUsersField.get_user_filter(self.request)
        self.group = self.request_params.get('group','')
        self.users = util.get_all_users_by_domain(self.domain, self.group, self.individual, self.user_filter)
        if not self.fields:
            self.hide_filters = True

        if self.individual and self.users:
            self.name = "%s for %s" % (self.name, self.users[0].raw_username)
        if self.show_time_notice:
            self.context.update(
                timezone_now = datetime.datetime.now(tz=self.timezone),
                timezone = self.timezone.zone
            )

        self.context.update(
            standard_report = True,
            layout_flush_content = True,
            report_hide_filters = self.hide_filters,
            report_breadcrumbs = self.custom_breadcrumbs,
            base_slug = self.base_slug
        )

    def get_global_params(self):
        self.process_basic()
        # the history param lets you run a report as if it were a given time in the past
        hist_param = self.request_params.get('history', None)
        if hist_param:
            self.history = datetime.datetime.strptime(hist_param, DATE_FORMAT)

        self.case_type = self.request_params.get('case_type', '')

        try:
            self.group = Group.get(self.group) if self.group else ''
        except Exception:
            pass

        self.get_parameters()

    def get_parameters(self):
        # here's where you can define any extra parameters you want to process before
        # proceeding with the rest of get_report_context
        pass

    def get_report_context(self):
        self.build_selector_form()
        self.context.update(util.report_context(self.domain,
                                        report_partial = self.report_partial,
                                        title = self.name,
                                        headers = self.headers,
                                        rows = self.rows,
                                        show_time_notice = self.show_time_notice
                                      ))
    
    def as_view(self):
        if self.asynchronous:
            self.process_basic()
        else:
            self.get_global_params()
        return super(StandardHQReport, self).as_view()

    def as_async(self, static_only=False):
        self.get_global_params()
        return super(StandardHQReport, self).as_async(static_only=static_only)

    def as_json(self):
        self.get_global_params()
        return super(StandardHQReport, self).as_json()


# TODO Make everything below a mixin instead of a subclass where possible...

class StandardTabularHQReport(StandardHQReport):
    total_row = None
    default_rows = 10
    start_at_row = 0
    fix_left_col = False
    fix_cols = dict(num=1, width=200)

    exportable = True

    def get_headers(self):
        return DataTablesHeader()

    def get_rows(self):
        return self.rows

    def get_report_context(self):
        self.context['report_datatables'] = {
            "defaultNumRows": self.default_rows,
            "startAtRowNum": self.start_at_row
        }
        if self.use_json:
            self.context['ajax_source'] = reverse('json_report_dispatcher',
                                                  args=[self.domain, self.slug])
            self.context['ajax_params'] = [dict(name='individual', value=self.individual),
                           dict(name='group', value=self.group),
                           dict(name='case_type', value=self.case_type),
                           dict(name='ufilter', value=[f.type for f in self.user_filter if f.show])]

        self.headers = self.get_headers()
        self.rows = self.get_rows()

        self.context['header'] = self.headers
        self.context['rows'] = self.rows
        if self.total_row:
            self.context['total_row'] = self.total_row

        super(StandardTabularHQReport, self).get_report_context()
        if self.fix_left_col:
            self.context['report']['fixed_cols'] = self.fix_cols

    def as_export(self):
        self.get_global_params()
        self.get_report_context()
        self.calc()
        try:
            import xlwt
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                        "excel export. To export to excel you have to run the "
                        "command:  easy_install xlutils")
        headers = self.get_headers()
        html_rows = self.get_rows()

        table = headers.as_table
        rows = []
        for row in html_rows:
            row = [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]
            rows.append(row)
        table.extend(rows)
        if self.total_row:
            total_row = [col.get("sort_key", col) if isinstance(col, dict) else col for col in self.total_row]
            table.append(total_row)

        table_format = [[self.name, table]]

        temp = StringIO()
        export_from_tables(table_format, temp, "xls")
        return export_response(temp, "xls", self.slug)


class PaginatedHistoryHQReport(StandardTabularHQReport):
    use_json = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']

    count = 0
    _total_count = None
    exportable = False
    
    @property
    def total_count(self):
        if self._total_count is not None:
            return self._total_count
        return self.count
    
    def get_parameters(self):
        self.userIDs = [user.user_id for user in self.users if user.user_id]
        self.usernames = dict([(user.user_id, user.username_in_report) for user in self.users])

    def json_data(self):
        params = DatatablesParams.from_request_dict(self.request.REQUEST)
        rows = self.paginate_rows(params.start, params.count)
        return {
            "sEcho": params.echo,
            "iTotalDisplayRecords": self.count,
            "iTotalRecords": self.total_count,
            "aaData": rows
        }

    def paginate_rows(self, skip, limit):
        # gather paginated rows here
        self.count = 0
        return []


class StandardDateHQReport(StandardHQReport):

    def __init__(self, domain, request, base_context=None):
        base_context = base_context or {}
        super(StandardDateHQReport, self).__init__(domain, request, base_context)
        self.datespan = self.get_default_datespan()
        self.datespan.is_default = True

    def get_default_datespan(self):
        return DateSpan.since(7, format="%Y-%m-%d", timezone=self.timezone)

    def process_basic(self):
        if self.request.datespan.is_valid() and not self.request.datespan.is_default:
            self.datespan.enddate = self.request.datespan.enddate
            self.datespan.startdate = self.request.datespan.startdate
            self.datespan.is_default = False
        self.datespan.timezone = self.timezone
        self.request.datespan = self.datespan
        self.context.update(dict(datespan=self.datespan))
        super(StandardDateHQReport, self).process_basic()
