"""
Custom report definitions - control display of reports.

The BaseReport is somewhat general, but it's
currently specific to monthly reports.  It would be pretty simple to make
this more general and subclass for montly reports , but I'm holding off on
that until we actually have another use case for it.
"""
from collections import defaultdict, OrderedDict
import datetime
import logging
import pickle
import json
import re
from dateutil import parser

from django.http import HttpResponse, HttpRequest, QueryDict
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _
from sqlagg.filters import RawFilter, IN, EQFilter
from couchexport.models import Format
from custom.common import ALL_OPTION

from dimagi.utils.couch.database import iter_docs, get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_request
from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn, SumColumn, CountUniqueColumn

from corehq.apps.es import cases as case_es, filters as es_filters
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.generic import ElasticTabularReport, GetParamsMixin
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn, DataFormatter, DictDataFormat
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin, DatespanMixin
from corehq.apps.reports.standard.maps import ElasticSearchMapReport
from corehq.apps.reports.util import make_form_couch_key
from corehq.apps.users.models import CommCareCase, CouchUser
from corehq.elastic import es_query
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.translation import localize
from dimagi.utils.couch import get_redis_client

from .utils import (BaseMixin, normal_format, format_percent,
                    get_matching_users, UserSqlData)
from .beneficiary import Beneficiary, ConditionsMet, OPMCaseRow
from .health_status import HealthStatus, AWCHealthStatus
from .incentive import Worker
from .filters import (HierarchyFilter, MetHierarchyFilter,
                      OPMSelectOpenCloseFilter as OpenCloseFilter)
from .constants import *


DATE_FILTER = "date between :startdate and :enddate"
DATE_FILTER_EXTENDED = """(
    opened_on <= :enddate AND (
        closed_on >= :enddate OR
        closed_on = ''
        )
    ) OR (
    opened_on <= :enddate AND (
        closed_on >= :startdate or closed_on <= :enddate
        )
    )
"""
DATE_FILTER_EXTENDED_OPENED = """(
    opened_on <= :enddate AND (
        closed_on >= :enddate OR
        closed_on = ''
        )
    )
"""
DATE_FILTER_EXTENDED_CLOSED = """(
    opened_on <= :enddate AND (
        closed_on <= :enddate AND
        closed_on != ''
        )
    )
"""

def ret_val(value):
    return value


class OpmCaseSqlData(SqlData):

    table_name = "fluff_OpmCaseFluff"

    def __init__(self, domain, user_id, datespan):
        self.domain = domain
        self.user_id = user_id
        self.datespan = datespan

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            user_id=self.user_id,
            startdate=str(self.datespan.startdate_utc.date()),
            enddate=str(self.datespan.enddate_utc.date())
        )

    @property
    def group_by(self):
        return ['user_id']

    @property
    def filters(self):
        filters = [
            "domain = :domain",
            "user_id = :user_id",
            DATE_FILTER_EXTENDED_OPENED,
        ]

        return filters

    @property
    def columns(self):
        return [
            DatabaseColumn("User ID", SimpleColumn("user_id")),
            DatabaseColumn("Women registered", SumColumn("women_registered_total")),
            DatabaseColumn("Children registered", SumColumn("children_registered_total"))
        ]

    @property
    def data(self):
        if self.user_id in super(OpmCaseSqlData, self).data:
            return super(OpmCaseSqlData, self).data[self.user_id]
        else:
            return None


class OpmFormSqlData(SqlData):
    table_name = "fluff_OpmFormFluff"

    def __init__(self, domain, user_id, datespan):
        self.domain = domain
        self.user_id = user_id
        self.datespan = datespan

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            user_id=self.user_id,
            startdate=self.datespan.startdate_utc.date(),
            enddate=self.datespan.enddate_utc.date()
        )

    @property
    def group_by(self):
        return ['user_id']

    @property
    def filters(self):
        filters = [
            "domain = :domain",
            "date between :startdate and :enddate"
        ]
        if self.user_id:
            filters.append("user_id = :user_id")
        return filters

    @property
    def columns(self):
        return [
            DatabaseColumn("User ID", SimpleColumn("user_id")),
            DatabaseColumn("Growth Monitoring Total", SumColumn("growth_monitoring_total")),
            DatabaseColumn("Service Forms Total", SumColumn("service_forms_total")),
        ]

    @property
    def data(self):
        if self.user_id is None:
            return super(OpmFormSqlData, self).data
        if self.user_id in super(OpmFormSqlData, self).data:
            return super(OpmFormSqlData, self).data[self.user_id]
        else:
            return None


VHND_PROPERTIES = [
    "vhnd_available",
    "vhnd_anm_present",
    "vhnd_asha_present",
    "vhnd_cmg_present",
    "vhnd_ifa_available",
    "vhnd_adult_scale_available",
    "vhnd_child_scale_available",
    "vhnd_adult_scale_functional",
    "vhnd_child_scale_functional",
    "vhnd_ors_available",
    "vhnd_zn_available",
    "vhnd_measles_vacc_available",
]

class VhndAvailabilitySqlData(SqlData):

    table_name = "fluff_VhndAvailabilityFluff"

    @property
    def filter_values(self):
        return {}

    @property
    def group_by(self):
        return ['owner_id', 'date']

    @property
    def filters(self):
        return []

    @property
    def columns(self):
        return [DatabaseColumn('date', SimpleColumn("date"))] +\
               [DatabaseColumn("", SumColumn(prop)) for prop in VHND_PROPERTIES]


class OpmHealthStatusSqlData(SqlData):

    table_name = 'fluff_OpmHealthStatusAllInfoFluff'

    def __init__(self, domain, user_id, datespan, case_status):
        self.domain = domain
        self.user_id = user_id
        self.datespan = datespan
        self.case_status = case_status

    @property
    def filter_values(self):
        filter = dict(
            domain=self.domain,
            user_id=self.user_id,
            startdate=str(self.datespan.startdate_utc.date()),
            enddate=str(self.datespan.enddate_utc.date()),
            lmp_total=1
        )
        return filter

    @property
    def group_by(self):
        return ['user_id']

    @property
    def filters(self):
        return [
            "domain = :domain",
            "user_id = :user_id"
        ]

    @property
    def wrapped_sum_column_filters(self):
        return self.wrapped_filters + [RawFilter(DATE_FILTER)]

    @property
    def wrapped_sum_column_filters_extended(self):
        filters = self.wrapped_filters
        if self.case_status == 'open':
            filters.extend([RawFilter(DATE_FILTER_EXTENDED_OPENED)])
        elif self.case_status == 'closed':
            filters.extend([RawFilter(DATE_FILTER_EXTENDED_CLOSED)])
        else:
            filters.extend([RawFilter(DATE_FILTER_EXTENDED)])
        return filters

    @property
    def columns(self):
        def AggColumn(label, alias, sum_slug, slug, extended=False):
            return AggregateColumn(
                label,
                format_percent,
                [
                    AliasColumn(alias),
                    SumColumn(
                        sum_slug,
                        filters=self.wrapped_sum_column_filters_extended
                                if extended else self.wrapped_sum_column_filters),
                ],
                slug=slug,
                format_fn=ret_val,
            )

        def GrowthMonitoringColumn(number):
            return AggColumn(
                "# of Children Who Have Attended At Least {} Growth Monitoring"
                "Session".format(number),
                alias='childrens',
                sum_slug='growth_monitoring_session_{}_total'.format(number),
                slug='growth_monitoring_session_{}'.format(number),
            )

        return [
            DatabaseColumn('# of Beneficiaries Registered',
                CountUniqueColumn('account_number',
                    alias="beneficiaries",
                    filters=self.wrapped_sum_column_filters_extended),
                format_fn=normal_format),
            AggregateColumn(
                '# of Pregnant Women Registered',
                format_percent,
                [
                    AliasColumn('beneficiaries'),
                    CountUniqueColumn(
                        'account_number',
                        filters=self.wrapped_sum_column_filters_extended + [EQFilter('lmp_total', 'lmp_total')]),
                ],
                slug='lmp',
                format_fn=ret_val,
            ),
            AggregateColumn('# of Mothers of Children Aged 3 Years and Below Registered',
                format_percent,
                [AliasColumn('beneficiaries'),
                    SumColumn('lactating_total',
                        # TODO necessary?
                        alias='mothers',
                        filters=self.wrapped_sum_column_filters_extended)],
                    slug='mother_reg',
                    format_fn=ret_val),
            DatabaseColumn('# of Children Between 0 and 3 Years of Age Registered',
                SumColumn('children_total',
                    alias="childrens",
                    filters=self.wrapped_sum_column_filters_extended),
                format_fn=normal_format),
            AggColumn(
                '# of Beneficiaries Attending VHND Monthly',
                alias='beneficiaries',
                sum_slug='vhnd_monthly_total',
                slug='vhnd_monthly',
            ),
            AggColumn(
                '# of Pregnant Women Who Have Received at least 30 IFA Tablets',
                alias='beneficiaries',
                sum_slug='ifa_tablets_total',
                slug='ifa_tablets',
            ),
            AggColumn(
                '# of Pregnant Women Whose Weight Gain Was Monitored At Least Once',
                alias='beneficiaries',
                sum_slug='weight_once_total',
                slug='weight_once',
            ),
            AggColumn(
                '# of Pregnant Women Whose Weight Gain Was Monitored Twice',
                alias='beneficiaries',
                sum_slug='weight_twice_total',
                slug='weight_twice',
            ),
            AggColumn(
                '# of Children Whose Weight Was Monitored at Birth',
                alias='childrens',
                sum_slug='children_monitored_at_birth_total',
                slug='children_monitored_at_birth',
            ),
            AggColumn(
                '# of Children Whose Birth Was Registered',
                alias='childrens',
                sum_slug='children_registered_total',
                slug='children_registered',
            ),
            GrowthMonitoringColumn(1),
            GrowthMonitoringColumn(2),
            GrowthMonitoringColumn(3),
            GrowthMonitoringColumn(4),
            GrowthMonitoringColumn(5),
            GrowthMonitoringColumn(6),
            GrowthMonitoringColumn(7),
            GrowthMonitoringColumn(8),
            GrowthMonitoringColumn(9),
            GrowthMonitoringColumn(10),
            GrowthMonitoringColumn(11),
            GrowthMonitoringColumn(12),
            AggColumn(
                '# of Children Whose Nutritional Status is Normal',
                alias='childrens',
                sum_slug='nutritional_status_normal_total',
                slug='nutritional_status_normal',
            ),
            AggColumn(
                '# of Children Whose Nutritional Status is "MAM"',
                alias='childrens',
                sum_slug='nutritional_status_mam_total',
                slug='nutritional_status_mam',
            ),
            AggColumn(
                '# of Children Whose Nutritional Status is "SAM"',
                alias='childrens',
                sum_slug='nutritional_status_sam_total',
                slug='nutritional_status_sam',
            ),
            AggregateColumn('# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea',
                    format_percent,
                    [SumColumn('treated_total',
                        filters=self.wrapped_sum_column_filters),
                        SumColumn('suffering_total',
                            filters=self.wrapped_sum_column_filters)],
                        slug='ors_zinc',
                        format_fn=ret_val),
            AggColumn(
                '# of Mothers of Children Aged 3 Years and Below Who Reported to Have Exclusively Breastfed Their Children for First 6 Months',
                alias='mothers',
                sum_slug='excbreastfed_total',
                slug="breastfed",
            ),
            AggColumn(
                '# of Children Who Received Measles Vaccine',
                alias='childrens',
                sum_slug='measlesvacc_total',
                slug='measlesvacc',
            ),
        ]


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

    def get_all_vhnd_forms(self):
        key = make_form_couch_key(DOMAIN, xmlns=VHND_XMLNS)
        return get_db().view(
            'reports_forms/all_forms',
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

    _debug_data = []
    @property
    def debug(self):
        return bool(self.request.GET.get('debug'))

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
        datetime_format = "%Y-%m-%d %H:%M:%S"
        subtitles.append("Generated {}".format(
            datetime.datetime.utcnow().strftime(datetime_format)))
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
            if len(t) == 3:
                headers.append(DataTablesColumn(name=t[1], visible=t[2]))
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
        for row in self.get_rows(self.datespan):
            try:
                rows.append(self.get_row_data(row))
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

    def get_model_kwargs(self):
        """
        Override this method to provide a dict of extra kwargs to the
        row constructor
        """
        return {}

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
    >>> _get_filter_list(terms)
    [["sahora"], ["kenar", "paharpur"], ["patear"]]
    """
    return filter(None, [term.lower().split() for term in terms])


def get_nested_terms_filter(prop, terms):
    filters = []

    def make_filter(term):
        return es_filters.term(prop, term)

    for term in _get_terms_list(terms):
        if len(term) == 1:
            filters.append(make_filter(term[0]))
        elif len(term) > 1:
            filters.append(es_filters.AND(*(make_filter(t) for t in term)))
    return es_filters.OR(*filters)


class CaseReportMixin(object):
    default_case_type = "Pregnancy"
    extra_row_objects = []
    is_rendered_as_email = False

    @memoized
    def column_index(self, key):
        for i, (k, _, _) in enumerate(self.model.method_map):
            if k == key:
                return i

    @property
    def case_status(self):
        return OpenCloseFilter.case_status(self.request_params)

    @property
    @memoized
    def users_matching_filter(self):
        return get_matching_users(self.awcs, self.gp, self.block)

    def get_rows(self, datespan):
        query = case_es.CaseES().domain(self.domain)\
                .fields([])\
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
            for doc in iter_docs(CommCareCase.get_db(), result.ids)
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
                        method, header, visible in self.model.method_map])

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
            row.serial_number = count
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
        return map(self.join_rows, accounts.values())

    def join_rows(self, rows):
        if len(rows) == 1:
            return rows[0]
        def zip_fn((i, values)):
            if isinstance(values[0], int):
                return sum(values)
            elif i == self.column_index('case_id'):
                unique_values = set(v for v in values if v is not None)
                if self.show_html:
                    return ''.join('<p>{}</p>'.format(v) for v in unique_values)
                else:
                    return ','.join(unique_values)
            elif i == self.column_index('issues'):
                sep = ', '
                msg = _("Duplicate account number")
                all_issues = sep.join(filter(None, values + (msg,)))
                return sep.join(set(all_issues.split(sep)))
            else:
                return sorted(values)[-1]
        return map(zip_fn, enumerate(zip(*rows)))


class MetReport(CaseReportMixin, BaseReport):
    name = ugettext_noop("Conditions Met Report")
    report_template_path = "opm/met_report.html"
    slug = "met_report"
    model = ConditionsMet
    exportable = False
    default_rows = 5
    ajax_pagination = True
    cache_key = 'opm-report'

    @property
    def row_objects(self):
        """
        Returns a list of objects, each representing a row in the report
        """
        rows = []
        self._debug_data = []
        awc_codes = {user['awc']: user['awc_code']
                     for user in UserSqlData().get_data()}
        for index, row in enumerate(self.get_rows(self.datespan), 1):
            try:
                rows.append(self.get_row_data(row, index=1, awc_codes=awc_codes))
            except InvalidRow as e:
                if self.debug:
                    import sys
                    import traceback
                    type, exc, tb = sys.exc_info()
                    self._debug_data.append({
                        'case_id': row._id,
                        'message': repr(e),
                        'traceback': ''.join(traceback.format_tb(tb)),
                    })
        return rows

    def get_row_data(self, row, **kwargs):
        return self.model(row, self, child_index=kwargs.get('index', 1), awc_codes=kwargs.get('awc_codes', {}))

    def get_rows(self, datespan):
        result = super(MetReport, self).get_rows(datespan)
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
    def total_records(self):
        return len(super(MetReport, self).rows)

    @property
    def headers(self):
        if not self.is_rendered_as_email:
            return DataTablesHeader(*[
                DataTablesColumn(name=header, visible=visible) for method, header, visible in self.model.method_map
            ])
        else:
            with localize('hin'):
                return DataTablesHeader(*[
                    DataTablesColumn(name=_(header), visible=visible) for method, header, visible
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
        self.pagination.count = 1000000

        cache = get_redis_client()
        if cache.exists(self.redis_key):
            rows = pickle.loads(cache.get(self.redis_key))
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

        if not self.is_rendered_as_email:
            return rows[self.pagination.start:(self.pagination.start + self.pagination.count)]
        else:
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
    report_template_path = "opm/beneficiary_report.html"
    # report_template_path = "opm/hsr_report.html"
    model = AWCHealthStatus

    def get_row_data(self, row, **kwargs):
        return OPMCaseRow(row, self)

    @property
    def headers(self):
        headers = []
        for __, title, text, __ in self.model.method_map:
            headers.append(DataTablesColumn(name=title, help_text=text))
        return DataTablesHeader(*headers)

    @property
    @request_cache("raw")
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
        pct = " ({:.0%})".format(float(val) / denom) if denom != 0 else ""
        return "{} / {}{}".format(val, denom, pct)

    @property
    def export_table(self):
        """
        Split the cells up into 3 for excel
        """
        def headers():
            headers = []
            for __, title, __, denom in self.model.method_map:
                if denom == 'no_denom':
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
                        row.append(float(value) / denom if denom != 0 else "")
                yield row

        self.pagination.count = 1000000
        table = headers().as_export_table
        table.extend(rows())
        return [[self.export_sheet_name, table]]


class UsersIdsData(SqlData):
    table_name = "fluff_OpmUserFluff"
    group_by = ['doc_id', 'name', 'awc', 'awc_code', 'bank_name',
                'ifs_code', 'account_number', 'gp', 'block', 'village']

    @property
    def filters(self):
        if self.config.get('awc'):
            return [IN('awc', 'awc')]
        elif self.config.get('gp'):
            return [IN('gp', 'gp')]
        elif self.config.get('block'):
            return [IN('block', 'block')]
        return []

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
            DatabaseColumn('village', SimpleColumn('village'))
        ]


class IncentivePaymentReport(BaseReport):
    name = "AWW Payment Report"
    slug = 'incentive_payment_report'
    model = Worker

    @property
    def fields(self):
        return [HierarchyFilter] + super(BaseReport, self).fields

    @property
    @memoized
    def last_month_totals(self):
        last_month = self.datespan.startdate_utc - datetime.timedelta(days=4)
        # TODO This feature depended on snapshots
        return None

    def get_model_kwargs(self):
        return {'last_month_totals': self.last_month_totals}

    def get_rows(self, datespan):
        config = {}
        for lvl in ['awc', 'gp', 'block']:
            req_prop = 'hierarchy_%s' % lvl
            request_param = self.request.GET.getlist(req_prop, [])
            if request_param and not request_param[0] == ALL_OPTION:
                config.update({lvl: tuple(self.request.GET.getlist(req_prop, []))})
                break
        return UsersIdsData(config=config).get_data()

    def get_row_data(self, row, **kwargs):
        case_sql_data = OpmCaseSqlData(DOMAIN, row['doc_id'], self.datespan)
        form_sql_data = OpmFormSqlData(DOMAIN, row['doc_id'], self.datespan)
        return self.model(row, self, case_sql_data.data, form_sql_data.data)


def this_month_if_none(month, year):
    if month is not None:
        assert year is not None, \
            "You must pass either nothing or a month AND a year"
        return month, year
    else:
        this_month = datetime.datetime.now()
        return this_month.month, this_month.year


class HealthStatusReport(DatespanMixin, BaseReport):

    ajax_pagination = True
    asynchronous = True
    name = "Health Status Report"
    slug = "health_status"
    fix_left_col = True
    model = HealthStatus
    report_template_path = "opm/hsr_report.html"

    @property
    def rows(self):
        ret = list(super(HealthStatusReport, self).rows)
        self.total_row = calculate_total_row(ret)
        return ret

    @property
    def fields(self):
        return [HierarchyFilter, OpenCloseFilter, DatespanFilter]

    @property
    def case_status(self):
        return OpenCloseFilter.case_status(self.request_params)

    @property
    @memoized
    def es_results(self):
        q = {
            "query": {
                "filtered": {
                    "query": {
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"domain.exact": self.domain}},
                            ]
                        }
                    }
                }
            },
            "size": self.pagination.count,
            "from": self.pagination.start,
        }
        es_filters = q["query"]["filtered"]["filter"]
        if self.awcs:
            awc_term = get_nested_terms_filter("user_data.awc", self.awcs)
            es_filters["bool"]["must"].append(awc_term)
        elif self.gp:
            gp_term = get_nested_terms_filter("user_data.gp", self.gp)
            es_filters["bool"]["must"].append(gp_term)
        elif self.blocks:
            block_term = get_nested_terms_filter("user_data.block", self.blocks)
            es_filters["bool"]["must"].append(block_term)
        q["query"]["filtered"]["query"].update({"match_all": {}})
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, json.dumps(q)))
        return es_query(q=q, es_url=USER_INDEX + '/_search', dict_only=False,
                        start_at=self.pagination.start, size=self.pagination.count)

    def get_rows(self, dataspan):
        return self.es_results['hits'].get('hits', [])

    def get_row_data(self, row, **kwargs):
        def empty_health_status(row):
            model = HealthStatus()
            model.awc = row['_source']['user_data']['awc']
            return model

        if 'user_data' in row['_source'] and 'awc' in row['_source']['user_data']:
            sql_data = OpmHealthStatusSqlData(DOMAIN, row['_id'], self.datespan, self.case_status)
            if sql_data.data:
                formatter = DataFormatter(DictDataFormat(sql_data.columns, no_value=format_percent(0, 0)))
                data = dict(formatter.format(sql_data.data, keys=sql_data.keys, group_by=sql_data.group_by))
                if row['_id'] not in data:
                    return empty_health_status(row)
                data[row['_id']].update({'awc': row['_source']['user_data']['awc']})
                return HealthStatus(**data[row['_id']])
            else:
                return empty_health_status(row)
        else:
            raise InvalidRow("AWC not found for case")

    @property
    def fixed_cols_spec(self):
        return dict(num=2, width=300)

    @property
    @request_cache()
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/hsr_print.html"
        self.update_report_context()
        self.pagination.count = 1000000
        self.context['report_table'].update(
            rows=self.rows
        )
        rendered_report = render_to_string(self.template_report, self.context,
            context_instance=RequestContext(self.request)
        )
        return HttpResponse(rendered_report)

    @property
    def export_table(self):
        """
        Exports the report as excel.

        When rendering a complex cell, it will assign a value in the following order:
        1. cell['raw']
        2. cell['sort_key']
        3. str(cell)
        """
        try:
            import xlwt
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                            "excel export. To export to excel you have to run the "
                            "command:  easy_install xlutils")
        self.pagination.count = 1000000
        headers = self.headers
        formatted_rows = self.rows


        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        table.extend(rows)
        if self.total_row:
            table.append(_unformat_row(self.total_row))
        if self.statistics_rows:
            table.extend([_unformat_row(row) for row in self.statistics_rows])

        return [[self.export_sheet_name, table]]


def calculate_total_row(rows):
    regexp = re.compile('(.*?)>([0-9]+)<.*')
    total_row = []
    if len(rows) > 0:
        num_cols = len(rows[0])
        for i in range(num_cols):
            colrows = [cr[i] for cr in rows]
            if i == 0:
                total_row.append("Total:")
            else:
                columns = [int(regexp.match(r).group(2)) for r in colrows]
                if len(columns):
                    total_row.append("<span style='display: block; text-align:center;'>%s</span>" % reduce(lambda x, y: x + y, columns, 0))
                else:
                    total_row.append('')
    return total_row


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


class HealthMapSource(HealthStatusReport):

    @property
    @memoized
    def get_users(self):
        return super(HealthMapSource, self).es_results['hits'].get('hits', [])

    @property
    def gps_mapping(self):
        users = self.get_users
        mapping = {}
        for user in users:
            user_src = user.get('_source', {})
            aww_name = user_src.get('first_name', "") + " " + user_src.get('last_name', "")
            meta_data = user_src.get('user_data', {})
            awc = meta_data.get("awc", "")
            block = meta_data.get("block", "")
            gp = meta_data.get("gp", "")
            gps = meta_data.get("gps", "")
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
            awc = row[0]
            awc_map = gps_mapping.get(awc, None) or ""
            gps = awc_map["gps"] if awc_map else "--"
            extra_columns = ["--"] * 4
            if awc_map:
                extra_columns = []
                for key in ["gps", "AWW", "Block", "GP"]:
                    extra_columns.append(awc_map.get(key, "--"))
            escaped_row = [row[0]]
            for cell in row[1:]:
                # _unformat_row([<html>] => ["N - f%"])
                percent = re.findall(pattern, _unformat_row([cell])[0])
                html_cell = {"html": cell, "sort_key": int(percent[0] if percent else 0)}
                escaped_row.append(html_cell)
            new_rows.append(extra_columns + escaped_row)
        return new_rows


class HealthMapReport(BaseMixin, ElasticSearchMapReport, GetParamsMixin, CustomProjectReport):
    name = "Health Status (Map)"
    slug = "health_status_map"

    fields = [HierarchyFilter, OpenCloseFilter, DatespanFilter]

    data_source = {
        'adapter': 'legacyreport',
        'geo_column': 'gps',
        'report': 'custom.opm.reports.HealthMapSource',
    }

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
            "Total # of Beneficiaries Registered",
            "# of Mothers of Children Aged 3 Years and Below Registered",
            "# of Children Between 0 and 3 Years of Age Registered",
            "# of Pregnant Women Who Have Received at least 30 IFA Tablets",
            "# of Pregnant Women Whose Weight Gain Was Monitored At Least Once",
            "# of Pregnant Women Whose Weight Gain Was Monitored Twice",
            "# of Children Whose Weight Was Monitored at Birth",
            "# of Children Who Have Attended At Least 1 Growth Monitoring Session",
            "# of Children Who Have Attended At Least 2 Growth Monitoring Sessions",
            "# of Children Who Have Attended At Least 3 Growth Monitoring Sessions",
            "# of Children Who Have Attended At Least 4 Growth Monitoring Sessions",
            '# of Children Who Have Attended At Least 5 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 6 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 7 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 8 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 9 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 10 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 11 Growth Monitoring Sessions',
            '# of Children Who Have Attended At Least 12 Growth Monitoring Sessions',
            '# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea',
            '# of Mothers of Children Aged 3 Years and Below Who Reported to Have Exclusively Breastfed Their Children for First 6 Months',
            '# of Children Who Received Measles Vaccine',
        ]
        columns = ["AWW", "Block", "GP"] + [
            "AWC",
            "# of Pregnant Women Registered",
            "# of Children Whose Birth Was Registered",
            "# of Beneficiaries Attending VHND Monthly",
            '# of Children Whose Nutritional Status is "SAM"',
            '# of Children Whose Nutritional Status is "MAM"',
            '# of Children Whose Nutritional Status is Normal'
        ]
        return {
            "detail_columns": columns[0:5],
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
