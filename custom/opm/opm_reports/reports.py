"""
Custom report definitions - control display of reports.

The BaseReport is somewhat general, but it's
currently specific to monthly reports.  It would be pretty simple to make
this more general and subclass for montly reports , but I'm holding off on
that until we actually have another use case for it.
"""
import datetime
import re
from couchdbkit.exceptions import ResourceNotFound
from dateutil import parser
from django.utils.translation import ugettext_noop
import simplejson
from sqlagg.columns import SimpleColumn, SumColumn
from corehq.apps.reports.cache import request_cache
from django.http import HttpResponse
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.generic import ElasticTabularReport, GetParamsMixin

from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin, DatespanMixin, \
    ProjectReportParametersMixin
from corehq.apps.reports.filters.select import SelectOpenCloseFilter, MonthFilter, YearFilter
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.reports.tasks import export_all_rows_task
from corehq.apps.users.models import CommCareCase, CouchUser
from dimagi.utils.dates import DateSpan
from corehq.elastic import es_query
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from custom.opm import HealthStatusMixin
from custom.opm.opm_reports.conditions_met import ConditionsMet
from custom.opm.opm_reports.filters import SelectBlockFilter, GramPanchayatFilter
from custom.opm.opm_reports.health_status import HealthStatus
from dimagi.utils.decorators.memoized import memoized

from ..opm_tasks.models import OpmReportSnapshot
from .beneficiary import Beneficiary
from .incentive import Worker
from .constants import *
from .filters import BlockFilter, AWCFilter
import logging
from corehq.apps.reports.standard.maps import GenericMapReport, ElasticSearchMapReport


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
            DatabaseColumn("Bp1 Cash Total", SumColumn("bp1_cash_total")),
            DatabaseColumn("Bp2 Cash Total", SumColumn("bp2_cash_total")),
            DatabaseColumn("Child Followup Total", SumColumn("child_followup_total")),
            DatabaseColumn("Child Spacing Deliveries", SumColumn("child_spacing_deliveries")),
            DatabaseColumn("Delivery Total", SumColumn("delivery_total")),
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

class OpmHealthStatusBasicInfoSqlData(SqlData):

    table_name = 'fluff_OpmHealthStatusBasicInfoFluff'

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
            DatabaseColumn('# of Beneficiaries Registered', SumColumn('beneficiaries_registered_total')),
            DatabaseColumn('# of Pregnant Women Registered', SumColumn('lmp_total')),
            DatabaseColumn('# of Mothers of Children Aged 3 Years and Below Registered', SumColumn('lactating_total')),
            DatabaseColumn('# of Children Between 0 and 3 Years of Age Registered', SumColumn('children_total')),
        ]

    @property
    def data(self):
        if self.user_id in super(OpmHealthStatusBasicInfoSqlData, self).data:
            return super(OpmHealthStatusBasicInfoSqlData, self).data[self.user_id]
        else:
            return None

class OpmHealthStatusSqlData(SqlData):

    table_name = 'fluff_OpmHealthStatusFluff'

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
            "user_id = :user_id",
            "date between :startdate and :enddate"
        ]

        return filters

    @property
    def columns(self):
        return [
            DatabaseColumn('# of Beneficiaries Attending VHND Monthly', SumColumn('vhnd_monthly_total')),
            DatabaseColumn('# of Pregnant Women Who Have Received at least 30 IFA Tablets', SumColumn('ifa_tablets_total')),
            DatabaseColumn('# of Pregnant Women Whose Weight Gain Was Monitored At Least Once', SumColumn('weight_once_total')),
            DatabaseColumn('# of Pregnant Women Whose Weight Gain Was Monitored Twice', SumColumn('weight_twice_total')),
            DatabaseColumn('# of Children Whose Weight Was Monitored at Birth', SumColumn('children_monitored_at_birth_total')),
            DatabaseColumn('# of Children Whose Birth Was Registered', SumColumn('children_registered_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 1 Growth Monitoring Session', SumColumn('growth_monitoring_session_1_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 2 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_2_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 3 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_3_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 4 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_4_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 5 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_5_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 6 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_6_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 7 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_7_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 8 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_8_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 9 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_9_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 10 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_10_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 11 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_11_total')),
            DatabaseColumn('# of Children Who Have Attended At Least 12 Growth Monitoring Sessions', SumColumn('growth_monitoring_session_12_total')),
            DatabaseColumn('# of Children Whose Nutritional Status is Normal', SumColumn('nutritional_status_normal_total')),
            DatabaseColumn('# of Children Whose Nutritional Status is "MAM"', SumColumn('nutritional_status_mam_total')),
            DatabaseColumn('# of Children Whose Nutritional Status is "SAM"', SumColumn('nutritional_status_sam_total')),
            DatabaseColumn('# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea', SumColumn('treated_total')),
            DatabaseColumn('# of Children Who Have Received ORS and Zinc Treatment if He/She Contracts Diarrhea', SumColumn('suffering_total')),
            DatabaseColumn('# of Mothers of Children Aged 3 Years and Below Who Reported to Have Exclusively Breastfed Their Children for First 6 Months', SumColumn('excbreastfed_total')),
            DatabaseColumn('# of Children Who Received Measles Vaccine', SumColumn('measlesvacc_total')),
        ]

    @property
    def data(self):
        if self.user_id in super(OpmHealthStatusSqlData, self).data:
            return super(OpmHealthStatusSqlData, self).data[self.user_id]
        else:
            return None

class BaseReport(MonthYearMixin, CustomProjectReport, ElasticTabularReport, ):
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
    default_rows = 50
    printable = True
    exportable = True
    exportable_all = True
    export_format_override = "csv"
    block = ''
    filter_fields = [('awc_name', 'awcs'), ('block', 'blocks')]

    @property
    def fields(self):
        return [BlockFilter, AWCFilter] + super(BaseReport, self).fields

    @property
    def report_subtitles(self):
        subtitles = ["For filters:",]
        if self.filter_data.get('blocks', []):
            subtitles.append("Blocks - %s" % ", ".join(self.filter_data.get('blocks', [])))
        if self.filter_data.get('awcs', []):
            subtitles.append("Awc's - %s" % ", ".join(self.filter_data.get('awcs', [])))
        startdate = self.datespan.startdate_param_utc
        enddate = self.datespan.enddate_param_utc
        if startdate and enddate:
            sd = parser.parse(startdate)
            ed = parser.parse(enddate)
            subtitles.append(" From %s to %s" % (str(sd.date()), str(ed.date())))
        return subtitles

    def filter(self, fn, filter_fields=None):
        """
        This function is to be called by the row constructer to verify that
        the row matches the filters
        ``fn`` should be a callable that accepts a key, and returns the value
        that should match the filters for a given field.

        I'm not super happy with this implementation, but it beats repeating
        the same logic in incentive, beneficiary, and snapshot.
        """
        if filter_fields is None:
            filter_fields = self.filter_fields
        for key, field in filter_fields:
            keys = self.filter_data.get(field, [])
            if keys and fn(key) not in keys:
                raise InvalidRow

    @property
    @memoized
    def snapshot(self):
        # Don't load snapshot if filtering by current case status,
        # instead, calculate again.
        if self.filter_data.get('is_open', False):
            return None
        return OpmReportSnapshot.from_view(self)


    @property
    def headers(self):
        if self.snapshot is not None:
            return DataTablesHeader(*[
                DataTablesColumn(header) for header in self.snapshot.headers if header != 'Bank Branch Name' # needed to support old snapshots
            ])
        return DataTablesHeader(*[
            DataTablesColumn(header) for method, header in self.model.method_map
        ])

    @property
    def rows(self):
        # is it worth noting whether or not the data being displayed is pulled
        # from an old snapshot?
        if self.snapshot is not None:
            # needed to support old snapshots
            if isinstance(self, BeneficiaryPaymentReport):
                for i, val in enumerate(self.snapshot.rows):
                    if 'bank_branch_name' in self.snapshot.slugs:
                        index = self.snapshot.slugs.index('bank_branch_name')
                        del self.snapshot.rows[i][index]
            return self.snapshot.rows
        rows = []
        for row in self.row_objects:
            rows.append([getattr(row, method) for
                method, header in self.model.method_map])
        return rows

    @property
    def filter_data(self):
        return dict([
            (field.slug, field.get_value(self.request, DOMAIN))
            for field in self.fields
        ])

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
    @request_cache("export")
    def export_response(self):
        export_all_rows_task.delay(self.__class__, self.__getstate__())

        return HttpResponse()

class BeneficiaryPaymentReport(BaseReport):
    name = "Beneficiary Payment Report"
    slug = 'beneficiary_payment_report'
    report_template_path = "opm/beneficiary_report.html"
    model = Beneficiary

    @property
    def fields(self):
        return super(BeneficiaryPaymentReport, self).fields + [SelectOpenCloseFilter]

    # TODO: Switch to ES. Peformance aaah!
    def get_rows(self, datespan):
        cases = []
        self.form_sql_data = OpmFormSqlData(domain=DOMAIN, case_id=None, datespan=self.datespan)
        for case_id in self.form_sql_data.data.keys():
            try:
                cases.append(CommCareCase.get(case_id))
            except ResourceNotFound:
                pass

        return [case for case in cases if self.passes_filter(case)]

    def passes_filter(self, case):
        status = self.filter_data.get('is_open', None)
        if status:
            if status == 'open' and not case.closed:
                return True
            elif status == 'closed' and case.closed:
                return True
            return False
        return True

    def get_row_data(self, row):
        return self.model(row, self, self.form_sql_data.data.__getitem__(row._id))


class IncentivePaymentReport(BaseReport):
    name = "AWW Payment Report"
    slug = 'incentive_payment_report'
    model = Worker

    @property
    @memoized
    def last_month_totals(self):
        last_month = self.datespan.startdate_utc - datetime.timedelta(days=4)
        snapshot = OpmReportSnapshot.by_month(last_month.month, last_month.year,
            "IncentivePaymentReport")
        if snapshot is not None:
            total_index = snapshot.slugs.index('month_total')
            account_index = snapshot.slugs.index('account_number')
            return dict(
                (row[account_index], row[total_index]) for row in snapshot.rows
            )

    def get_model_kwargs(self):
        return {'last_month_totals': self.last_month_totals}

    def get_rows(self, datespan):
        return CommCareUser.by_domain(DOMAIN)

    def get_row_data(self, row):
        case_sql_data = OpmCaseSqlData(DOMAIN, row._id, self.datespan)
        form_sql_data = OpmFormSqlData(DOMAIN, row._id, self.datespan)
        return self.model(row, self, case_sql_data.data, form_sql_data.data)


def last_if_none(month, year):
    if month is not None:
        assert year is not None, \
            "You must pass either nothing or a month AND a year"
        return month, year
    else:
        last_month = datetime.datetime.now() - datetime.timedelta(days=27)
        return last_month.month, last_month.year


def get_report(ReportClass, month=None, year=None, block=None):
    """
    Utility method to run a report for an arbitrary month without a request
    """
    month, year = last_if_none(month, year)
    class Report(ReportClass):
        snapshot = None
        report_class = ReportClass
        domain = DOMAIN
        visible_cols = []

        def __init__(self, *args, **kwargs):
            if ReportClass.__name__ == "MetReport":
                self.slugs, self._headers, self.visible_cols = [list(tup) for tup in zip(*self.model.method_map[self.block])]
            else:
                self.slugs, self._headers = [list(tup) for tup in zip(*self.model.method_map)]

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
        def datespan(self):
            return DateSpan.from_month(month, year)

        @property
        def filter_data(self):
            return {}

    return Report()


class HealthStatusReport(HealthStatusMixin, GetParamsMixin, BaseReport, DatespanMixin):

    ajax_pagination = True
    asynchronous = True
    name = "Health Status Report"
    slug = "health_status_report"
    fix_left_col = True
    model = HealthStatus

    @property
    def rows(self):
        ret = list(super(HealthStatusReport, self).rows)
        self.total_row = calculate_total_row(ret)
        return ret

    @property
    def fields(self):
        return [BlockFilter, AWCFilter, SelectOpenCloseFilter, DatespanFilter]

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
        if self.blocks:
            block_lower = [block.lower() for block in self.blocks]
            es_filters["bool"]["must"].append({"terms": {"user_data.block": block_lower}})
        if self.awcs:
            awcs_lower = [awc.lower() for awc in self.awcs]
            awc_term = {
                "or":
                    [{"and": [{"term": {"user_data.awc": term}} for term in re.split('\s', awc)
                                if not re.search(r'^\W+$', term) or re.search(r'^\w+', term)]
                    } for awc in awcs_lower]
            }
            es_filters["bool"]["must"].append(awc_term)
        q["query"]["filtered"]["query"].update({"match_all": {}})
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))
        return es_query(q=q, es_url=USER_INDEX + '/_search', dict_only=False,
                        start_at=self.pagination.start, size=self.pagination.count)

    def get_rows(self, dataspan):
        return self.es_results['hits'].get('hits', [])


    def get_row_data(self, row):
        if 'user_data' in row['_source'] and 'awc' in row['_source']['user_data']:
            basic_info = OpmHealthStatusBasicInfoSqlData(DOMAIN, row['_id'], self.datespan)
            sql_data = OpmHealthStatusSqlData(DOMAIN, row['_id'], self.datespan)
        else:
            raise InvalidRow
        return self.model(row['_source'], self, basic_info.data, sql_data.data)

    @property
    @request_cache("raw")
    def print_response(self):
        """
        Returns the report for printing.
        """
        self.is_rendered_as_email = True
        self.use_datatables = False
        self.override_template = "opm/hsr_print.html"
        return HttpResponse(self._async_context()['report'])

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

class MetReport(BaseReport):
    name = ugettext_noop("Conditions Met Report")
    report_template_path = "opm/met_report.html"
    slug = "met_report"
    model = ConditionsMet
    exportable = False
    default_case_type = "Pregnancy"
    filter_fields = [('awc_name', 'awcs'), ('owner_id', 'gp'), ('closed', 'is_open')]

    @property
    def report_subtitles(self):
        subtitles = ["For filters:",]
        if self.block:
            subtitles.append("Block - %s" % self.block)
        if self.filter_data.get('awcs', []):
            subtitles.append("Awc's - %s" % ", ".join(self.filter_data.get('awcs', [])))
        if self.filter_data.get('gp', ''):
            subtitles.append("Gram Panchayat - %s" % self.filter_data.get('gp', ''))
        startdate = self.datespan.startdate_param_utc
        enddate = self.datespan.enddate_param_utc
        if startdate and enddate:
            sd = parser.parse(startdate)
            ed = parser.parse(enddate)
            subtitles.append(" From %s to %s" % (str(sd.date()), str(ed.date())))
        return subtitles


    @property
    def block(self):
        block = self.request_params.get("block")
        if block:
            return block
        else:
            return 'atri'


    @property
    def fields(self):
        return [
            SelectBlockFilter,
            AWCFilter,
            GramPanchayatFilter,
            MonthFilter,
            YearFilter,
            SelectOpenCloseFilter
        ]

    @property
    def headers(self):
        if self.snapshot is not None:
            return DataTablesHeader(*[
                DataTablesColumn(name=header[0], visible=header[1]) for header in zip(self.snapshot.headers, self.snapshot.visible_cols)
            ])
        return DataTablesHeader(*[
            DataTablesColumn(name=header, visible=visible) for method, header, visible in self.model.method_map[self.block.lower()]
        ])

    @property
    @memoized
    def users(self):
        return CouchUser.by_domain(self.domain) if self.filter_data.get('gp', []) else []

    @property
    def rows(self):
        if self.snapshot is not None:
            return self.snapshot.rows
        rows = []
        for row in self.row_objects:
            rows.append([getattr(row, method) for
                method, header, visible in self.model.method_map[self.block.lower()]])
        return rows

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

    def get_rows(self, datespan):
        block = self.block
        q = {
            "query": {
                "filtered": {
                    "query": {
                        "match_all": {},
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"domain.exact": self.domain}},
                                {"term": {"block_name.#value": block.lower()}}
                            ]
                        }
                    }
                }
            }
        }
        es_filters = q["query"]["filtered"]["filter"]
        if self.snapshot is None:
            awcs = self.request.GET.getlist('awcs')
            if awcs:
                awcs_lower = [awc.lower() for awc in awcs]
                awc_term = {
                    "or":
                        [{"and": [{"term": {"awc_name.#value": term}} for term in re.split('\s', awc)
                                    if not re.search(r'^\W+$', term) or re.search(r'^\w+', term)]
                        } for awc in awcs_lower]
                }
                es_filters["bool"]["must"].append(awc_term)
            gp = self.request_params.get('gp', None)
            if gp:
                users = CouchUser.by_domain(self.domain)
                users_id = [user._id for user in users if 'user_data' in user and 'gp' in user.user_data and user.user_data['gp'] == gp]
                es_filters["bool"]["must"].append({"terms": {"owner_id": users_id}})
            is_open = self.request_params.get('is_open', None)
            if is_open:
                es_filters["bool"]["must"].append({"term": {"closed": is_open == 'closed'}})
        if self.default_case_type:
            es_filters["bool"]["must"].append({"term": {"type.exact": self.default_case_type}})
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))
        return es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=False)['hits'].get('hits', [])


    def get_row_data(self, row):
        return self.model(row, self)

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
    def snapshot(self):
        # Don't attempt to load a snapshot
        return None


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


class HealthMapReport(HealthStatusMixin, ElasticSearchMapReport, GetParamsMixin, CustomProjectReport):
    name = "Health Status (Map)"
    slug = "health_status_map"

    fields = [BlockFilter, AWCFilter, SelectOpenCloseFilter, DatespanFilter]

    data_source = {
        'adapter': 'legacyreport',
        'geo_column': 'gps',
        'report': 'custom.opm.opm_reports.reports.HealthMapSource',
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
