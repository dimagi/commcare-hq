from collections import defaultdict, OrderedDict
from itertools import chain
import datetime
import pickle
import re
import urllib
from dateutil import parser
from dateutil.rrule import MONTHLY, rrule

from django.http import HttpResponse, Http404
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _
from sqlagg.filters import IN
from corehq.apps.style.decorators import use_maps
from corehq.const import SERVER_DATETIME_FORMAT
from couchexport.models import Format
from couchforms.models import XFormInstance
from custom.opm.utils import numeric_fn
from custom.utils.utils import clean_IN_filter_value

from casexml.apps.case.models import CommCareCase
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.decorators.memoized import memoized
from sqlagg.columns import SimpleColumn

from corehq.apps.es import cases as case_es, filters as es_filters
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.generic import ElasticTabularReport, GetParamsMixin
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.maps import GenericMapReport
from corehq.apps.reports.util import (
    get_INFilter_bindparams,
    make_form_couch_key,
)
from corehq.apps.users.models import CouchUser
from corehq.util.translation import localize
from dimagi.utils.couch import get_redis_client

from .utils import (BaseMixin, get_matching_users)
from .beneficiary import Beneficiary, ConditionsMet, OPMCaseRow, LongitudinalConditionsMet
from .health_status import AWCHealthStatus
from .incentive import Worker
from .filters import (HierarchyFilter, MetHierarchyFilter,
                      OPMSelectOpenCloseFilter as OpenCloseFilter)
from .constants import *


class SharedDataProvider(object):
    """
    Data provider for report data that can be shared across rows in an instance
    of a report.
    """
    vhnd_form_props = [
        'attend_ANM',
        'attend_ASHA',
        'attend_cmg',
        'big_weight_machine_avail',
        'child_weight_machine_avail',
        'func_bigweighmach',
        'func_childweighmach',
        'stock_ifatab',
        'stock_measlesvacc',
        'stock_ors',
        'stock_zntab',
    ]

    def __init__(self, cases=None):
        self.cases = cases

    def get_all_vhnd_forms(self):
        key = make_form_couch_key(DOMAIN, xmlns=VHND_XMLNS)
        return XFormInstance.get_db().view(
            'all_forms/view',
            startkey=key,
            endkey=key+[{}],
            reduce=False,
            include_docs=True
        ).all()

    @property
    @memoized
    def case_owners(self):
        q = (case_es.CaseES()
             .domain(DOMAIN)
             .case_type('vhnd')
             .fields(['owner_id', '_id']))
        return {
            case['_id']: case['owner_id']
            for case in q.run().hits
            if (case.get('_id') and case.get('owner_id'))
        }

    @property
    @memoized
    def _service_dates(self):
        """
        returns {
            u'df5123010b24fc35260a84547148af06': {
                'ifa_available': {datetime.date(2013, 1, 14),
                                  datetime.date(2013, 8, 23)}
                'zn_available': {datetime.date(2013, 1, 14)}
            }
        }
        """
        forms = self.get_all_vhnd_forms()
        results = defaultdict(lambda: defaultdict(lambda: set()))
        for form in forms:
            source = form['doc'].get('form', {})
            raw_date = source.get('date_vhnd_held', None)
            if not raw_date:
                continue
            vhnd_date = parser.parse(raw_date).date()
            case_id = source.get('case', {}).get('@case_id')
            # case_id might be for a deleted case :(
            if case_id in self.case_owners:
                owner_id = self.case_owners[case_id]
                owner_id = owner_id[0] if isinstance(owner_id, list) else owner_id
                results[owner_id]['vhnd_available'].add(vhnd_date)
                for prop in self.vhnd_form_props:
                    if source.get(prop, None) == '1':
                        results[owner_id][prop].add(vhnd_date)
        return results

    def get_dates_in_range(self, owner_id, startdate, enddate, prop='vhnd_available'):
        return filter(
            lambda vhnd_date: vhnd_date >= startdate and vhnd_date < enddate,
            [date for date in self._service_dates[owner_id][prop]],
        )

    @property
    @memoized
    def forms_by_case(self):
        assert self.cases is not None, \
            "SharedDataProvider was not instantiated with cases"
        all_form_ids = chain(*(case.xform_ids for case in self.cases))
        forms_by_case = defaultdict(list)
        for form in iter_docs(XFormInstance.get_db(), all_form_ids):
            if form['xmlns'] in OPM_XMLNSs:
                case_id = form['form']['case']['@case_id']
                forms_by_case[case_id].append(XFormInstance.wrap(form))
        return forms_by_case


class BaseReport(BaseMixin, GetParamsMixin, MonthYearMixin, CustomProjectReport, ElasticTabularReport):
    """
    Report parent class.  Children must provide a get_rows() method that
    returns a list of the raw data that forms the basis of each row.

    The "model" attribute is an object that can accept raw_data for a row
    and perform the neccessary calculations.  It must also provide a
    method_map that is a list of (method_name, "Verbose Title") tuples
    that define the columns in the report.
    """
    name = None
    slug = None
    model = None
    report_template_path = "opm/report.html"
    printable = True
    exportable = True
    exportable_all = False
    export_format_override = Format.UNZIPPED_CSV
    block = ''
    is_cacheable = True
    include_out_of_range_cases = False

    _debug_data = []

    @property
    def debug(self):
        return bool(self.request.GET.get('debug'))

    @property
    def export_name(self):
        return "%s %s/%s" % (super(BaseReport, self).export_name, self.request.GET.get('month'),
                             self.request.GET.get('year'))

    @property
    def show_html(self):
        return getattr(self, 'rendered_as', 'html') not in ('print', 'export')

    @property
    def fields(self):
        return [HierarchyFilter] + super(BaseReport, self).fields

    @property
    def report_subtitles(self):
        subtitles = ["For filters:",]
        if self.filter_data.get('awc', []):
            subtitles.append("Awc's - %s" % ", ".join(self.awcs))
        if self.filter_data.get('gp', []):
            subtitles.append("Gram Panchayat - %s" % ", ".join(self.gp))
        if self.filter_data.get('block', []):
            subtitles.append("Blocks - %s" % ", ".join(self.blocks))
        startdate = self.datespan.startdate_param_utc
        enddate = self.datespan.enddate_param_utc
        if startdate and enddate:
            sd = parser.parse(startdate)
            ed = parser.parse(enddate)
            subtitles.append(" From %s to %s" % (str(sd.date()), str(ed.date())))
        subtitles.append("Generated {}".format(
            datetime.datetime.utcnow().strftime(SERVER_DATETIME_FORMAT)))
        return subtitles

    def filter(self, fn, filter_fields=None):
        """
        This function is to be called by the row constructer to verify that
        the row matches the filters
        ``fn`` should be a callable that accepts a key, and returns the value
        that should match the filters for a given field.

        I'm not super happy with this implementation, but it beats repeating
        the same logic everywhere
        """
        if filter_fields is None:
            filter_fields = self.filter_fields
        for key, field in filter_fields:
            keys = self.filter_data.get(field, [])
            value = fn(key) if (fn(key) is not None) else ""
            if field == 'gp':
                keys = [user._id for user in self.users if 'user_data' in user and 'gp' in user.user_data and
                        user.user_data['gp'] and user.user_data['gp'] in keys]
            if keys and value not in keys:
                raise InvalidRow("Case does not match filters")

    @property
    def filter_fields(self):
        filter_by = []
        if self.awcs:
            filter_by = [('awc_name', 'awc')]
        elif self.gp:
            filter_by = [('owner_id', 'gp')]
        elif self.block:
            if isinstance(self, BeneficiaryPaymentReport):
                filter_by = [('block_name', 'block')]
            else:
                filter_by = [('block', 'block')]
        return filter_by

    @property
    def headers(self):
        headers = []
        for t in self.model.method_map:
            if self.model == Worker or self.model == Beneficiary:
                headers.append(DataTablesColumn(name=t[1], visible=t[2], sort_type=t[3]))
            else:
                headers.append(DataTablesColumn(name=t[1]))
        return DataTablesHeader(*headers)

    @property
    def rows(self):
        rows = []
        for row in self.row_objects:
            data = []
            for t in self.model.method_map:
                data.append(getattr(row, t[0]))
            rows.append(data)

        return rows

    @property
    @memoized
    def filter_data(self):
        fields = []
        for field in self.fields:
            value = field.get_value(self.request, DOMAIN)
            if isinstance(value, tuple):
                for lvl in field.get_value(self.request, DOMAIN)[0]:
                    fields.append((lvl['slug'], lvl['value']))
            else:
                fields.append((field.slug, field.get_value(self.request, DOMAIN)))
        return dict(fields)

    @property
    def row_objects(self):
        """
        Returns a list of objects, each representing a row in the report
        """
        rows = []
        self._debug_data = []
        for row in self.get_rows():
            try:
                case = self.get_row_data(row)
                if self.include_out_of_range_cases or not case.case_is_out_of_range:
                    rows.append(case)
                else:
                    if self.debug:
                        self._debug_data.append({
                            'case_id': row._id,
                            'message': _('Reporting period incomplete'),
                            'traceback': _('Reporting period incomplete'),
                        })
            except InvalidRow as e:
                if self.debug:
                    import sys, traceback
                    type, exc, tb = sys.exc_info()
                    self._debug_data.append({
                        'case_id': row._id,
                        'message': repr(e),
                        'traceback': ''.join(traceback.format_tb(tb)),
                    })
        return rows

    def get_row_data(self, row):
        return self.model(row, self)

    @property
    def date_range(self):
        start = self.datespan.startdate_utc
        end = self.datespan.enddate_utc
        now = datetime.datetime.utcnow()
        # if report is run on current month, date range should be
        # this month up till now
        if start.year == now.year and start.month == now.month:
            end = now
        return (start, end)

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/print_report.html"
        return HttpResponse(self._async_context()['report'])

    @property
    @memoized
    def users(self):
        return CouchUser.by_domain(self.domain) if self.filter_data.get('gp', []) else []

    @property
    @memoized
    def data_provider(self):
        return SharedDataProvider()


def _get_terms_list(terms):
    """
    >>> terms = ["Sahora", "Kenar Paharpur", "   ", " Patear"]
    >>> _get_terms_list(terms)
    [['sahora'], ['kenar', 'paharpur'], ['patear']]
    """
    return filter(None, [term.lower().split() for term in terms])


class CaseReportMixin(object):
    default_case_type = "Pregnancy"
    extra_row_objects = []
    is_rendered_as_email = False

    @memoized
    def column_index(self, key):
        for i, (k, _1, _2, _3) in enumerate(self.model.method_map):
            if k == key:
                return i

    @property
    def case_status(self):
        return OpenCloseFilter.case_status(self.request_params)

    @property
    @memoized
    def users_matching_filter(self):
        return get_matching_users(self.awcs, self.gp, self.block)

    def get_rows(self):
        return self.cases

    @property
    @memoized
    def cases(self):
        if 'debug_case' in self.request.GET:
            case = CommCareCase.get(self.request.GET['debug_case'])
            if case.domain != DOMAIN:
                raise Http404()
            return [case]

        query = case_es.CaseES().domain(self.domain)\
                .exclude_source()\
                .opened_range(lte=self.datespan.enddate_utc)\
                .case_type(self.default_case_type)
        query.index = 'report_cases'

        if self.case_status == 'open':
            query = query.filter(es_filters.OR(
                case_es.is_closed(False),
                case_es.closed_range(gte=self.datespan.enddate_utc)
            ))
        elif self.case_status == 'closed':
            query = query.filter(case_es.closed_range(lte=self.datespan.enddate_utc))

        query = query.owner([user['doc_id'] for user in self.users_matching_filter])

        result = query.run()

        return [
            CommCareCase.wrap(doc)
            for doc in iter_docs(CommCareCase.get_db(), result.doc_ids)
        ]

    @property
    def fields(self):
        return [
            MetHierarchyFilter,
            MonthFilter,
            YearFilter,
            OpenCloseFilter,
        ]

    @property
    def block(self):
        block = self.request_params.get("hierarchy_block")
        if block:
            return block
        else:
            return 'atri'

    @property
    def rows(self):
        rows = []
        sorted_objects = self.sort_and_set_serial_numbers(self.row_objects + self.extra_row_objects)
        for row in sorted_objects:
            rows.append([getattr(row, method) for
                        method, header, visible, sort_type in self.model.method_map])

        if self.debug:
            def _debug_item_to_row(debug_val):
                num_cols = len(self.model.method_map) - 3
                return [debug_val['case_id'], debug_val['message'], debug_val['traceback']] + [''] * num_cols

            rows.extend([_debug_item_to_row(dbv) for dbv in self._debug_data])

        return rows

    def sort_and_set_serial_numbers(self, case_objects):
        # sets serial_number for each row as the index in cases list sorted by awc_name, name
        from operator import attrgetter
        sorted_rows = sorted(case_objects, key=attrgetter('awc_name', 'name'))
        for count, row in enumerate(sorted_rows, 1):
            row.serial_number = numeric_fn(count)
        return sorted_rows

    def filter(self, fn, filter_fields=None):
        if filter_fields is None:
            filter_fields = self.filter_fields
        for key, field in filter_fields:
            keys = self.filter_data.get(field, [])
            if keys:
                case_key = fn(key)['#value'] if isinstance(fn(key), dict) else fn(key)
                if field == 'is_open':
                    if case_key != (keys == 'closed'):
                        raise InvalidRow("Case doesn't match filters")
                else:
                    if field == 'gp':
                        keys = [user._id for user in self.users if 'user_data' in user and 'gp' in user.user_data and user.user_data['gp'] in keys]
                    if case_key not in keys:
                        raise InvalidRow("Case doesn't match filters")

    def set_extra_row_objects(self, row_objects):
        self.extra_row_objects = self.extra_row_objects + row_objects

    @property
    @memoized
    def data_provider(self):
        return SharedDataProvider(self.cases)


class BeneficiaryPaymentReport(CaseReportMixin, BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    report_template_path = "opm/beneficiary_report.html"
    model = Beneficiary

    @property
    def rows(self):
        raw_rows = super(BeneficiaryPaymentReport, self).rows
        if self.debug:
            return raw_rows

        # Consolidate rows with the same account number
        accounts = OrderedDict()
        for row in raw_rows:
            account_number = row[self.column_index('account_number')]
            existing_row = accounts.get(account_number, [])
            accounts[account_number] = existing_row + [row]
        return map(lambda x: list(self.join_rows(x)), accounts.values())

    def join_rows(self, rows):
        if len(rows) == 1:
            for cel in rows[0]:
                yield cel
        else:
            has_bonus_cash = 0
            share_account = False
            for i, values in enumerate(zip(*rows)):
                if i == self.column_index('num_children'):
                    yield values[0]
                elif i == self.column_index('year_end_bonus_cash'):
                    has_bonus_cash = values[0]
                    yield has_bonus_cash
                elif isinstance(values[0], int):
                    yield sum(values)
                elif i == self.column_index('case_id'):
                    unique_values = set(v for v in values if v is not None)
                    share_account = len(unique_values) > 1
                    if self.show_html:
                        yield ''.join('<p>{}</p>'.format(v) for v in unique_values)
                    else:
                        yield ','.join(unique_values)
                elif i == self.column_index('issues'):
                    sep = ', '
                    msg = ''
                    if share_account:
                        if has_bonus_cash == 2000 or has_bonus_cash == 3000:
                            msg = _("Check for multiple pregnancies")
                        else:
                            msg = _("Duplicate account number")
                    all_issues = sep.join(filter(None, values + (msg,)))
                    yield sep.join(set(all_issues.split(sep)))
                else:
                    yield sorted(values)[-1]


class MetReport(CaseReportMixin, BaseReport):
    name = ugettext_noop("Conditions Met Report")
    report_template_path = "opm/met_report.html"
    slug = "met_report"
    model = ConditionsMet
    default_rows = 5
    cache_key = 'opm-report'
    show_total = True
    exportable = True

    @property
    def row_objects(self):
        """
        Returns a list of objects, each representing a row in the report
        """
        rows = []
        self._debug_data = []
        total_payment = 0
        for index, row in enumerate(self.get_rows(), 1):
            try:
                case_row = self.get_row_data(row, index=1)
                if not case_row.case_is_out_of_range:
                    total_payment += case_row.cash_amt
                    rows.append(case_row)
                else:
                    case_row.one = ''
                    case_row.two = ''
                    case_row.three = ''
                    case_row.four = ''
                    case_row.five = ''
                    case_row.pay = '--'
                    case_row.payment_last_month = '--'
                    case_row.cash = '--'
                    case_row.issue = _('Reporting period incomplete')
                    rows.append(case_row)
            except InvalidRow as e:
                if self.debug:
                    self.add_debug_data(row._id, e)
        if self.show_total:
            self.total_row = ["" for __ in self.model.method_map]
            self.total_row[0] = _("Total Payment")
            self.total_row[self.column_index('cash')] = "Rs. {}".format(total_payment)
        return rows

    def add_debug_data(self, row_id, e):
        import sys
        import traceback
        type, exc, tb = sys.exc_info()
        self._debug_data.append({
            'case_id': row_id,
            'message': repr(e),
            'traceback': ''.join(traceback.format_tb(tb)),
        })

    def get_row_data(self, row, **kwargs):
        return self.model(row, self, child_index=kwargs.get('index', 1))

    def get_rows(self):
        result = super(MetReport, self).get_rows()
        result.sort(key=lambda case: [
            case.get_case_property(prop)
            for prop in ['block_name', 'village_name', 'awc_name']
        ])
        return result

    @property
    def redis_key(self):
        redis_key = self.cache_key + "_" + self.slug
        redis_key += "?blocks=%s&gps=%s&awcs=%s" % (self.blocks, self.gp, self.awcs)
        redis_key += "&year=%s&month=%s&is_open=%s" % (
            self.request_params.get('year'),
            self.request_params.get('month'),
            self.request_params.get('is_open'),
        )
        return redis_key

    @property
    def headers(self):
        if not self.is_rendered_as_email:
            return DataTablesHeader(*[
                DataTablesColumn(name=header, visible=visible, sort_type=sort_type)
                for method, header, visible, sort_type in self.model.method_map
            ])
        else:
            with localize('hin'):
                return DataTablesHeader(*[
                    DataTablesColumn(name=_(header), visible=visible) for method, header, visible, sort_type
                    in self.model.method_map if method != 'case_id' and method != 'closed_date'
                ])

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/met_print_report.html"
        self.update_report_context()

        cache = get_redis_client()
        value = cache.get(self.redis_key)
        if value is not None:
            rows = pickle.loads(value)
        else:
            rows = self.rows

        """
        Strip user_id and owner_id columns
        """
        for row in rows:
            with localize('hin'):
                row[self.column_index('readable_status')] = _(row[self.column_index('readable_status')])
                row[self.column_index('cash_received_last_month')] = _(row[self.column_index(
                    'cash_received_last_month')])
            del row[self.column_index('closed_date')]
            del row[self.column_index('case_id')]
            link_text = re.search('<a href=.*>(.*)</a>', row[self.column_index('name')])
            if link_text:
                row[self.column_index('name')] = link_text.group(1)

        rows.sort(key=lambda r: r[self.column_index('serial_number')])
        total_row = self.total_row

        with localize('hin'):
            total_row[0] = _(total_row[0])

        rows.append(total_row)

        self.context['report_table'].update(
            rows=rows
        )
        rendered_report = render_to_string(self.template_report, self.context,
                                           context_instance=RequestContext(self.request))
        return HttpResponse(rendered_report)

    def _store_rows_in_redis(self, rows):
        r = get_redis_client()
        r.set(self.redis_key, pickle.dumps(rows))
        r.expire(self.slug, 60 * 60)

    @property
    def rows(self):
        sort_cols = int(self.request.GET.get('iSortingCols', 0))
        col_id = None
        sort_dir = None
        if sort_cols > 0:
            for x in range(sort_cols):
                col_key = 'iSortCol_%d' % x
                sort_dir = self.request.GET['sSortDir_%d' % x]
                col_id = int(self.request.GET[col_key])
        rows = super(MetReport, self).rows
        if sort_dir == 'asc':
            rows.sort(key=lambda x: x[col_id])
        elif sort_dir == 'desc':
            rows.sort(key=lambda x: x[col_id], reverse=True)
        self._store_rows_in_redis(rows)
        return rows


class NewHealthStatusReport(CaseReportMixin, BaseReport):
    """
    This is a reimagining of the Health Status report as a simple aggregator
    of the data source for the MetReport and BeneficiaryPaymentReport.
    If it is accepted, we should rename this to HealthStatusReport and delete
    the old HSR.

    It uses the base OPMCaseRow as the row model, then does some after-the-fact
    aggregation based on the AWCHealthStatus model.
    """
    name = "New Health Status Report"
    slug = 'health_status_report'
    report_template_path = "opm/new_hsr_report.html"
    model = AWCHealthStatus
    fix_left_col = True

    def get_row_data(self, row, **kwargs):
        return OPMCaseRow(row, self)

    @property
    def fields(self):
        return [
            HierarchyFilter,
            MonthFilter,
            YearFilter,
            OpenCloseFilter,
        ]

    @property
    def fixed_cols_spec(self):
        return dict(num=7, width=600)

    @property
    def headers(self):
        headers = []
        for __, title, text, __ in self.model.method_map:
            headers.append(DataTablesColumn(name=title, help_text=text))
        return DataTablesHeader(*headers)

    @property
    @request_cache()
    def print_response(self):
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/new_hsr_print.html"
        self.update_report_context()
        self.pagination.count = 1000000
        headers = self.headers
        for h in headers:
            if h.help_text:
                h.html = "%s (%s)" % (h.html, h.help_text)
                h.help_text = None

        self.context['report_table'].update(
            headers=headers
        )
        rendered_report = render_to_string(self.template_report, self.context,
                                           context_instance=RequestContext(self.request))
        return HttpResponse(rendered_report)

    @property
    @memoized
    def awc_data(self):
        case_objects = self.row_objects + self.extra_row_objects
        cases_by_owner = {}
        for case_object in case_objects:
            owner_id = case_object.owner_id
            cases_by_owner[owner_id] = cases_by_owner.get(owner_id, []) + [case_object]
        return cases_by_owner

    def iter_awcs(self):
        for user in self.users_matching_filter:
            yield AWCHealthStatus(
                cases=self.awc_data.get(user['doc_id'], []),
                awc=user['awc'],
                awc_code=user['awc_code'],
                gp=user['gp'],
                block=user['block'],
            )

    @property
    def rows(self):
        totals = [[None, None] for i in range(len(self.model.method_map))]

        def add_to_totals(col, val, denom):
            for i, num in enumerate([val, denom]):
                if isinstance(num, int):
                    total = totals[col][i]
                    totals[col][i] = total + num if total is not None else num

        rows = []
        for awc in self.iter_awcs():
            row = []
            for col, (method, __, __, denom) in enumerate(self.model.method_map):
                val = getattr(awc, method)
                denominator = getattr(awc, denom, None)
                row.append(self.format_cell(val, denominator))
                if denom is 'one':
                    add_to_totals(col, val, 1)
                else:
                    add_to_totals(col, val, denominator)
            rows.append(row)

        self.total_row = [self.format_cell(v, d) for v, d in totals]
        return rows

    def format_cell(self, val, denom):
        if denom is None:
            return val if val is not None else ""
        if val == "NA":
            return "NA"
        try:
            pct = " ({:.0%})".format(float(val) / denom) if denom != 0 else ""
        except TypeError:
            return "NA"
        return "{} / {}{}".format(val, denom, pct)

    @property
    def export_table(self):
        """
        Split the cells up into 3 for excel
        """
        def headers():
            headers = []
            for __, title, __, denom in self.model.method_map:
                if denom == 'no_denom' or denom == 'one':
                    headers.append(DataTablesColumn(name=title))
                else:
                    for template in [u"{}", u"{} - denominator", u"{} - percent"]:
                        headers.append(DataTablesColumn(name=template.format(title)))
            return DataTablesHeader(*headers)

        def rows():
            for awc in self.iter_awcs():
                row = []
                for method, __, __, denom in self.model.method_map:
                    value = getattr(awc, method)
                    row.append(value)
                    if denom != 'no_denom' and denom != 'one':
                        denom = getattr(awc, denom)
                        row.append(denom)
                        row.append(float(value) / denom if denom != 0 and value != "NA" else "")
                yield row

        self.pagination.count = 1000000
        table = headers().as_export_table
        table.extend(rows())
        return [[self.export_sheet_name, table]]


class UsersIdsData(SqlData):
    table_name = "fluff_OpmUserFluff"
    group_by = ['doc_id', 'name', 'awc', 'awc_code', 'bank_name',
                'ifs_code', 'account_number', 'gp', 'block', 'village', 'gps']

    @property
    def filters(self):
        for column_name in ['awc', 'gp', 'block']:
            if self.config.get(column_name):
                return [IN(column_name, get_INFilter_bindparams(column_name, self.config[column_name]))]
        return []

    @property
    def filter_values(self):
        filter_values = super(UsersIdsData, self).filter_values
        for column_name in ['awc', 'gp', 'block']:
            if filter_values.get(column_name):
                return clean_IN_filter_value(filter_values, column_name)
        return filter_values

    @property
    def columns(self):
        return [
            DatabaseColumn('doc_id', SimpleColumn('doc_id')),
            DatabaseColumn('name', SimpleColumn('name')),
            DatabaseColumn('awc', SimpleColumn('awc')),
            DatabaseColumn('awc_code', SimpleColumn('awc_code')),
            DatabaseColumn('bank_name', SimpleColumn('bank_name')),
            DatabaseColumn('ifs_code', SimpleColumn('ifs_code')),
            DatabaseColumn('account_number', SimpleColumn('account_number')),
            DatabaseColumn('gp', SimpleColumn('gp')),
            DatabaseColumn('block', SimpleColumn('block')),
            DatabaseColumn('village', SimpleColumn('village')),
            DatabaseColumn('gps', SimpleColumn('gps'))
        ]


class IncentivePaymentReport(CaseReportMixin, BaseReport):
    name = "AWW Payment Report"
    slug = 'incentive_payment_report'
    model = Worker
    include_out_of_range_cases = True

    @property
    def headers(self):
        headers = super(IncentivePaymentReport, self).headers
        if self.debug:
            headers.add_column(DataTablesColumn(name='Debug Info'))
        return headers

    @property
    def fields(self):
        return [HierarchyFilter] + super(BaseReport, self).fields

    @property
    @memoized
    def awc_data(self):
        """
        Returns a map of user IDs to lists of wrapped CommCareCase objects that those users own.
        """
        case_objects = self.row_objects + self.extra_row_objects
        cases_by_owner = {}
        for case_object in case_objects:
            owner_id = case_object.owner_id
            cases_by_owner[owner_id] = cases_by_owner.get(owner_id, []) + [case_object]
        return cases_by_owner

    @property
    def rows(self):
        rows = []
        for user in self.users_matching_filter:
            user_case_list = self.awc_data.get(user['doc_id'], None)
            row = self.model(user, self, user_case_list)
            data = []
            for t in self.model.method_map:
                data.append(getattr(row, t[0]))
            if self.debug:
                data.append(row.debug_info)
            rows.append(data)
        return rows

    def get_row_data(self, row, **kwargs):
        return OPMCaseRow(row, self)


def _unformat_row(row):
    regexp = re.compile('(.*?)>([0-9]+)(<.*?)>([0-9]*).*')
    formatted_row = []
    for col in row:
        if isinstance(col, basestring) and regexp.match(col):
            formated_col = "%s" % (regexp.match(col).group(2))
            if regexp.match(col).group(4) != "":
                formated_col = "%s - %s%%" % (formated_col, regexp.match(col).group(4))
            formatted_row.append(formated_col)
        else:
            formatted_row.append(col)
    return formatted_row


class HealthMapSource(NewHealthStatusReport):

    total_rows = 0

    @property
    @memoized
    def get_users(self):
        awcs = [awc.split('-')[0].strip() for awc in self.awcs]
        config = {
            'awc': tuple(awcs),
            'gp': tuple(self.gp),
            'block': tuple(self.blocks)
        }
        return UsersIdsData(config=config).get_data()

    @property
    def gps_mapping(self):
        users = self.get_users
        mapping = {}
        for user in users:
            aww_name = user['name']
            awc = user['awc']
            block = user['block']
            gp = user['gp']
            gps = user['gps']
            mapping[awc] = {
                "AWW": aww_name,
                "Block": block,
                "GP": gp,
                "gps": gps
            }
        return mapping

    @property
    def headers(self):
        ret = super(HealthMapSource, self).headers
        for key in ["GP", "Block", "AWW", "gps"]:
            ret.prepend_column(DataTablesColumn(key))
        return ret

    @property
    def rows(self):
        pattern = re.compile("(\d+)%")
        gps_mapping = self.gps_mapping
        ret = super(HealthMapSource, self).rows
        new_rows = []
        for row in ret:
            awc = row[1]
            awc_map = gps_mapping.get(awc, None) or ""
            extra_columns = ["--"] * 4
            if awc_map:
                extra_columns = []
                for key in ["gps", "AWW", "Block", "GP"]:
                    extra_columns.append(awc_map.get(key, "--"))
            escaped_row = ['', row[1]]
            for cell in row[2:]:
                # _unformat_row([<html>] => ["N - f%"])
                try:
                    percent = re.findall(pattern, _unformat_row([cell])[0])
                    html_cell = {"html": cell, "sort_key": int(percent[0] if percent else 0)}
                except TypeError:
                    html_cell = {"html": cell, "sort_key": cell}
                escaped_row.append(html_cell)
            new_rows.append(extra_columns + escaped_row)
        return new_rows


class HealthMapReport(BaseMixin, GenericMapReport, GetParamsMixin, CustomProjectReport, MonthYearMixin):
    name = "Health Status (Map)"
    title = "Health Status (Map)"
    slug = "health_status_map"
    fields = [HierarchyFilter, MonthFilter, YearFilter, OpenCloseFilter]
    report_partial_path = "opm/map_template.html"
    base_template = 'opm/map_base_template.html'
    printable = True

    data_source = {
        'adapter': 'legacyreport',
        'geo_column': 'gps',
        'report': 'custom.opm.reports.HealthMapSource',
    }

    is_bootstrap3 = True

    @use_maps
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(HealthMapReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def report_subtitles(self):
        subtitles = ["For filters:"]
        awcs = self.request.GET.getlist('hierarchy_awc', [])
        gps = self.request.GET.getlist('hierarchy_gp', [])
        blocks = self.request.GET.getlist('hierarchy_block', [])
        if awcs:
            subtitles.append("Awc's - %s" % ", ".join(awcs))
        if gps:
            subtitles.append("Gram Panchayat - %s" % ", ".join(gps))
        if blocks:
            subtitles.append("Blocks - %s" % ", ".join(blocks))
        startdate = self.datespan.startdate
        enddate = self.datespan.enddate
        subtitles.append(" From %s to %s" % (startdate, enddate))
        subtitles.append("Generated {}".format(
            datetime.datetime.utcnow().strftime(SERVER_DATETIME_FORMAT)))
        return subtitles

    @property
    def display_config(self):
        colorstops = [
            [40, 'rgba(255, 0, 0, .8)'],
            [70, 'rgba(255, 255, 0, .8)'],
            [100, 'rgba(0, 255, 0, .8)']
        ]
        reverse_colorstops = [
            [40, 'rgba(0, 255, 0, .8)'],
            [70, 'rgba(255, 255, 0, .8)'],
            [100, 'rgba(255, 0, 0, .8)'],
        ]
        title_mapping = {
                "AWC": "AWC",
                "# of Pregnant Women Registered": "Pregnant Women Registered",
                "# of Children Whose Birth Was Registered": "Children Whose Birth Was Registered",
                "# of Beneficiaries Attending VHND Monthly": "Beneficiaries Attending VHND Monthly",
                '# of Children Whose Nutritional Status is "SAM"': 'Children Whose Nutritional Status is "SAM"',
                '# of Children Whose Nutritional Status is "MAM"': 'Children Whose Nutritional Status is "MAM"',
                '# of Children Whose Nutritional Status is Normal': 'Children Whose Nutritional Status is Normal'
        }
        additional_columns = [
            "Registered Beneficiaries",
            "Registered children",
            "Child birth registered",
            "Received at least 30 IFA tablets",
            "Weight monitored in second trimester",
            "Weight monitored in third trimester",
            "Weight monitored at birth",
            "Growth monitoring when 0-3 months old",
            "Growth Monitoring when 4-6 months old",
            "Growth Monitoring when 7-9 months old",
            "Growth Monitoring when 10-12 months old",
            "Growth Monitoring when 13-15 months old",
            "Growth Monitoring when 16-18 months old",
            "Growth Monitoring when 19-21 months old",
            "Growth Monitoring when 22-24 months old",
            "Received ORS and Zinc treatment for diarrhoea",
            "Exclusively breastfed for first 6 months",
            "Received Measles vaccine",
        ]
        columns = ["AWW", "Block", "GP"] + [
            "AWC Name",
            "Registered pregnant women",
            "Registered children",
            "Pregnant women attended VHND",
            'Severely underweight',
            'Underweight',
            'Normal weight for age'
        ]
        config = {
            "detail_columns": columns[:5],
            "display_columns": columns[4:],
            "table_columns": columns,
            "column_titles": title_mapping,
            "metrics": [{"color": {"column": column}} for column in columns[:4]] + [
                {"color": {"column": column, "colorstops": colorstops}} for column in columns[4:-3] + columns[-1:0]
            ] + [
                {"color": {"column": column, "colorstops": reverse_colorstops}} for column in columns[-3:-1]
            ] + [
                {"color": {"column": column, "colorstops": colorstops}} for column in additional_columns
            ],
            "numeric_format": {
                title: "return x + ' \%'" for title in additional_columns + columns[4:]
            }
        }
        default_metric = self.request.GET.get('metric', None)
        if default_metric:
            for metric in config['metrics']:
                unquote = urllib.unquote(default_metric)
                if metric['color']['column'] == unquote:
                    metric['default'] = True
                    break
        return config

    @property
    def rows(self):
        data = self._get_data()
        columns = self.display_config['table_columns']
        display_columns = self.display_config['display_columns']
        rows = []

        for feature in data['features']:
            row = []
            for column in columns:
                if column in feature['properties'] and column not in display_columns:
                    row.append(feature['properties'][column])
                else:
                    disp_col = '__disp_' + column
                    if disp_col in feature['properties']:
                        row.append(feature['properties'][disp_col])
            rows.append(row)
        return rows

    @property
    def headers(self):
        columns = self.display_config['table_columns']
        headers = DataTablesHeader(*[
            DataTablesColumn(name=name, sortable=False) for name in columns]
        )
        return headers

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/map_template.html"

        return HttpResponse(self._async_context()['report'])


class LongitudinalCMRReport(MetReport):
    name = "Longitudinal CMR"
    slug = 'longitudinal_cmr'
    model = LongitudinalConditionsMet
    show_total = False
    exportable = True
    export_format_override = Format.XLS
    month = None
    year = None

    @property
    def row_objects(self):
        """
        Returns a list of objects, each representing a row in the report
        """
        rows = []
        self._debug_data = []
        now = datetime.datetime.now()
        for index, row in enumerate(self.get_rows(), 1):
            months = list(
                rrule(MONTHLY, dtstart=datetime.date(row.opened_on.year, row.opened_on.month, 1),
                      until=datetime.date(now.year, now.month, 1))
            )
            for month in months:
                self.month = month.month
                self.year = month.year
                try:
                    case_row = self.get_row_data(row, index=1)
                    if not case_row.case_is_out_of_range:
                        rows.append(case_row)
                    else:
                        case_row.one = ''
                        case_row.two = ''
                        case_row.three = ''
                        case_row.four = ''
                        case_row.five = ''
                        case_row.pay = '--'
                        case_row.payment_last_month = '--'
                        case_row.issue = _('Reporting period incomplete')
                        rows.append(case_row)
                except InvalidRow as e:
                    if self.debug:
                        self.add_debug_data(row._id, e)
        return rows

    @property
    def fields(self):
        return [
            MetHierarchyFilter,
            OpenCloseFilter,
        ]

    @property
    def redis_key(self):
        redis_key = self.cache_key + "_" + self.slug
        redis_key += "?blocks=%s&gps=%s&awcs=%s&is_open=%s" % (
            self.blocks,
            self.gp,
            self.awcs,
            self.request_params.get('is_open')
        )
        return redis_key
