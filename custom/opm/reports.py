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
import simplejson
import re
from dateutil import parser

from django.http import HttpResponse, HttpRequest, QueryDict
from django.template import RequestContext
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop, ugettext as _
from sqlagg.filters import RawFilter, IN
from couchexport.models import Format

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.web import json_request
from sqlagg.base import AliasColumn
from sqlagg.columns import SimpleColumn, SumColumn

from corehq.apps.es import cases as case_es, filters as es_filters
from corehq.apps.reports.cache import request_cache
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.select import SelectOpenCloseFilter, MonthFilter, YearFilter
from corehq.apps.reports.generic import ElasticTabularReport, GetParamsMixin
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData, AggregateColumn, DataFormatter, DictDataFormat
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin, DatespanMixin
from corehq.apps.reports.standard.maps import ElasticSearchMapReport
from corehq.apps.users.models import CommCareCase, CouchUser, CommCareUser
from corehq.elastic import es_query
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.translation import localize

from .utils import BaseMixin, normal_format, format_percent
from .beneficiary import Beneficiary, ConditionsMet
from .health_status import HealthStatus
from .incentive import Worker
from .filters import HierarchyFilter, MetHierarchyFilter
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
            "(opened_on <= :enddate AND (closed_on >= :enddate OR closed_on = '')) OR (opened_on <= :enddate AND (closed_on >= :startdate or closed_on <= :enddate))"
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

    def __init__(self, domain, case_id, datespan):
        self.domain = domain
        self.case_id = case_id
        self.datespan = datespan

    @property
    def filter_values(self):
        return dict(
            domain=self.domain,
            case_id=self.case_id,
            startdate=self.datespan.startdate_utc.date(),
            enddate=self.datespan.enddate_utc.date()
        )

    @property
    def group_by(self):
        return ['case_id']

    @property
    def filters(self):
        filters = [
            "domain = :domain",
            "date between :startdate and :enddate"
        ]
        if self.case_id:
            filters.append("case_id = :case_id")
        return filters

    @property
    def columns(self):
        return [
            DatabaseColumn("Case ID", SimpleColumn("case_id")),
            DatabaseColumn("Growth Monitoring Total", SumColumn("growth_monitoring_total")),
            DatabaseColumn("Service Forms Total", SumColumn("service_forms_total")),
        ]

    @property
    def data(self):
        if self.case_id is None:
            return super(OpmFormSqlData, self).data
        if self.case_id in super(OpmFormSqlData, self).data:
            return super(OpmFormSqlData, self).data[self.case_id]
        else:
            return None


VHND_PROPERTIES = [
    "vhnd_available",
    "vhnd_ifa_available",
    "vhnd_adult_scale_available",
    "vhnd_child_scale_available",
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
            enddate=str(self.datespan.enddate_utc.date()),
        )

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
        return self.wrapped_filters + [RawFilter(DATE_FILTER_EXTENDED)]

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
                SumColumn('beneficiaries_registered_total',
                    alias="beneficiaries",
                    filters=self.wrapped_sum_column_filters_extended),
                format_fn=normal_format),
            AggColumn(
                '# of Pregnant Women Registered',
                alias='beneficiaries',
                sum_slug='lmp_total',
                slug='lmp',
                extended=True,
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
        # TODO: this will load one row per every VHND in history.
        # If this gets too big we'll have to make the queries more targeted (which would be
        # easy to do in the get_dates_in_range function) but if the dataset is small this will
        # avoid significantly fewer DB trips.
        # If things start getting slow or memory intensive this would be a good place to look.
        data = VhndAvailabilitySqlData().data
        results = defaultdict(lambda: defaultdict(lambda: set()))
        for (owner_id, date), row in data.iteritems():
            if row['vhnd_available'] > 0:
                for prop in VHND_PROPERTIES:
                    if row[prop] == '1' or prop == 'vhnd_available':
                        results[owner_id][prop].add(date)
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
                raise InvalidRow

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
        for row in self.get_rows(self.datespan):
            try:
                rows.append(self.get_row_data(row))
            except InvalidRow:
                pass
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
    @request_cache("raw")
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

    @property
    def display_open_cases_only(self):
        return self.request_params.get('is_open') == 'open'

    @property
    def display_closed_cases_only(self):
        return self.request_params.get('is_open') == 'closed'

    def get_rows(self, datespan):
        def get_awc_filter(awcs):
            return get_nested_terms_filter("awc_name.#value", awcs)

        def get_gp_filter(gp):
            owner_ids = [user._id for user in self.users
                         if getattr(user, 'user_data', {}).get('gp') in self.gp]
            return es_filters.term("owner_id", owner_ids)

        def get_block_filter(block):
            return es_filters.term("block_name.#value", block.lower())

        query = case_es.CaseES().domain(self.domain)\
                .fields([])\
                .opened_range(lte=self.datespan.enddate_utc)\
                .term("type.exact", self.default_case_type)
        query.index = 'report_cases'

        if self.display_open_cases_only:
            query = query.filter(es_filters.OR(
                case_es.is_closed(False),
                case_es.closed_range(gte=self.datespan.enddate_utc)
            ))
        elif self.display_closed_cases_only:
            query = query.filter(case_es.closed_range(lte=self.datespan.enddate_utc))

        if self.awcs:
            query = query.filter(get_awc_filter(self.awcs))
        elif self.gp:
            query = query.filter(get_gp_filter(self.gp))
        elif self.block:
            query = query.filter(get_block_filter(self.block))
        result = query.run()
        return map(CommCareCase, iter_docs(CommCareCase.get_db(), result.ids))

    @property
    def fields(self):
        return [
            MetHierarchyFilter,
            MonthFilter,
            YearFilter,
            SelectOpenCloseFilter,
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
        for row in self.row_objects + self.extra_row_objects:
            rows.append([getattr(row, method) for
                method, header, visible in self.model.method_map])

        sorted_rows = sorted(rows, key=lambda item: item[0])
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
                        raise InvalidRow
                else:
                    if field == 'gp':
                        keys = [user._id for user in self.users if 'user_data' in user and 'gp' in user.user_data and user.user_data['gp'] in keys]
                    if case_key not in keys:
                        raise InvalidRow

    def set_extra_row_objects(self, row_objects):
        self.extra_row_objects = self.extra_row_objects + row_objects


class BeneficiaryPaymentReport(CaseReportMixin, BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    report_template_path = "opm/beneficiary_report.html"
    model = Beneficiary

    @memoized
    def column_index(self, key):
        for i, (k, _, _) in enumerate(self.model.method_map):
            if k == key:
                return i

    @property
    def rows(self):
        raw_rows = super(BeneficiaryPaymentReport, self).rows
        # Consolidate rows with the same account number
        accounts = OrderedDict()
        for row in raw_rows:
            account_number = row[self.column_index('account_number')]
            existing_row = accounts.get(account_number, [])
            accounts[account_number] = existing_row + [row]
        return map(self.join_rows, accounts.values())

    def join_rows(self, rows):
        def zip_fn((i, values)):
            if isinstance(values[0], int):
                return sum(values)
            elif i == self.column_index('case_id'):
                unique_values = set(v for v in values if v is not None)
                if self.show_html:
                    return ''.join('<p>{}</p>'.format(v) for v in unique_values)
                else:
                    return ','.join(unique_values)
            else:
                return sorted(values)[-1]
        return map(zip_fn, enumerate(zip(*rows)))


class MetReport(CaseReportMixin, BaseReport):
    name = ugettext_noop("Conditions Met Report")
    report_template_path = "opm/met_report.html"
    slug = "met_report"
    fix_left_col = True
    model = ConditionsMet
    exportable = False

    @property
    def headers(self):
        if not self.is_rendered_as_email:
            return DataTablesHeader(*[
                DataTablesColumn(name=header, visible=visible) for method, header, visible in self.model.method_map
            ])
        else:
            with localize('hin'):
                return DataTablesHeader(*[
                    DataTablesColumn(name=_(header), visible=visible) for method, header, visible in self.model.method_map
                ])

    @property
    @request_cache("raw")
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/met_print_report.html"
        return HttpResponse(self._async_context()['report'])

    @property
    def fixed_cols_spec(self):
        return dict(num=9, width=800)

class UsersIdsData(SqlData):
    table_name = "fluff_OpmUserFluff"
    group_by = ['doc_id', 'awc', 'awc_code', 'bank_name', 'ifs_code', 'account_number', 'gp', 'block', 'village']

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
        config={}
        for lvl in ['awc', 'gp', 'block']:
            req_prop = 'hierarchy_%s' % lvl
            request_param = self.request.GET.getlist(req_prop, [])
            if request_param and not request_param[0] == '0':
                config.update({lvl: tuple(self.request.GET.getlist(req_prop, []))})
                break
        return UsersIdsData(config=config).get_data()

    def get_row_data(self, row):
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


def get_report(ReportClass, month=None, year=None, block=None, lang=None):
    """
    Utility method to run a report for an arbitrary month without a request
    """
    month, year = this_month_if_none(month, year)
    class Report(ReportClass):
        report_class = ReportClass
        _visible_cols = []

        def __init__(self, *args, **kwargs):
            if ReportClass.__name__ in ["MetReport", "BeneficiaryPaymentReport"]:
                self._slugs, self._headers, self._visible_cols = [
                    list(tup) for tup in zip(*self.model.method_map)
                ]
                for idx, val in enumerate(self._headers):
                    with localize(self.lang):
                        self._headers[idx] = _(self._headers[idx])
            elif ReportClass.__name__ == "IncentivePaymentReport":
                self._slugs, self._headers, self._visible_cols = [list(tup) for tup in zip(*self.model.method_map)]
            else:
                self._slugs, self._headers = [list(tup) for tup in zip(*self.model.method_map)]

        @property
        def domain(self):
            return DOMAIN

        @property
        def slugs(self):
            return self._slugs

        @property
        def visible_cols(self):
            return self._visible_cols

        @property
        def month(self):
            return month

        @property
        def year(self):
            return year

        @property
        def block(self):
            return block

        @property
        def headers(self):
            return self._headers

        @property
        def lang(self):
            return lang

        @property
        def datespan(self):
            return DateSpan.from_month(self.month, self.year)

        @property
        def filter_data(self):
            return {}

        @property
        def request(self):
            request = HttpRequest()
            request.GET = QueryDict(None)
            return request

        @property
        def request_params(self):
            return json_request({})

    return Report()


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
        return [HierarchyFilter, SelectOpenCloseFilter, DatespanFilter]

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
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))
        return es_query(q=q, es_url=USER_INDEX + '/_search', dict_only=False,
                        start_at=self.pagination.start, size=self.pagination.count)

    def get_rows(self, dataspan):
        return self.es_results['hits'].get('hits', [])

    def get_row_data(self, row):
        def empty_health_status(row):
            model = HealthStatus()
            model.awc = row['_source']['user_data']['awc']
            return model

        if 'user_data' in row['_source'] and 'awc' in row['_source']['user_data']:
            sql_data = OpmHealthStatusSqlData(DOMAIN, row['_id'], self.datespan)
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
            raise InvalidRow

    @property
    def fixed_cols_spec(self):
        return dict(num=2, width=300)

    @property
    @request_cache("raw")
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
        if regexp.match(col):
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
            user_src = user['_source']
            aww_name = user_src['first_name'] + " " + user_src['last_name']
            meta_data = user_src['user_data']
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

    fields = [HierarchyFilter, SelectOpenCloseFilter, DatespanFilter]

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
