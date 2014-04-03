from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop
import simplejson
from corehq.apps.api.es import ReportCaseES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.select import MonthFilter, YearFilter, SelectOpenCloseFilter
from corehq.apps.reports.standard import CustomProjectReport, MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.elastic import es_query
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from custom.opm.opm_reports.display import AtriDisplay, WazirganjDisplay
from custom.opm.opm_reports.filters import SelectBlockFilter, AWCFilter, GramPanchayatFilter
import logging


class MetReport(CustomProjectReport, CaseListReport, MonthYearMixin):
    name = ugettext_noop("Conditions Met Report")
    slug = "met_report"
    report_template_path = 'opm/met_report.html'
    default_case_type = "Pregnancy"

    fields = [
        SelectBlockFilter,
        AWCFilter,
        GramPanchayatFilter,
        MonthFilter,
        YearFilter,
        SelectOpenCloseFilter
    ]

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    @property
    def block(self):
        return self.request_params.get("block")

    @property
    @memoized
    def es_results(self):

        block = self.block
        awcs = self.request.GET.getlist("awcs")
        gp = self.request_params.get("gp")
        startdate = self.datespan.startdate_param_utc
        enddate = self.datespan.enddate_param_utc
        q = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"domain.exact": self.domain}}
                    ],
                    "must_not": []
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start,
            'size': self.pagination.count,
        }

        query = q['query']['bool']['must']

        if block:
            query.append({'match': {'block_name.#value': block}})
        if awcs:
            terms = {"terms": {"awc_name.#value": awcs, "minimum_should_match": 1}}
            query.append(terms)
        if self.default_case_type:
            query.append({"match": {"type.exact": self.default_case_type}})
        logging.info("ESlog: [%s.%s] ESquery: %s" % (self.__class__.__name__, self.domain, simplejson.dumps(q)))
        return es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=False)

    @property
    def headers(self):
        block = self.block
        headers = DataTablesHeader(
                DataTablesColumn(_('List of Beneficiary')),
                DataTablesColumn(_('AWC Name')),
                DataTablesColumn(_("Month")),
                DataTablesColumn(_("Window")),
                DataTablesColumn(_("1")),
                DataTablesColumn(_("2")),
                DataTablesColumn(_("3")),
                DataTablesColumn(_("4")),
                DataTablesColumn(_("Cash to be transferred"))
        )

        if block.lower() == 'atri':
            headers.insert_column(DataTablesColumn(_("Husband Name")), 2)
            headers.insert_column(DataTablesColumn(_("5")), 9)
        elif block.lower() == 'wazirganj':
            headers.insert_column(DataTablesColumn(_("Current status")), 2)
        return headers

    @property
    @memoized
    def case_users_and_owners(self):
        return [], []

    @property
    def rows(self):
        block = self.block
        if block.lower() == 'atri':
            case_displays = (AtriDisplay(self, self.get_case(case))
                for case in self.es_results['hits'].get('hits', []))
            for disp in case_displays:
                yield [
                    disp.case_name,
                    disp.awc,
                    disp.husband_name,
                    disp.month,
                    disp.window,
                    disp.one,
                    disp.two,
                    disp.three,
                    disp.four,
                    disp.five,
                    disp.cash_to_transferred

                ]
        elif block.lower() == 'wazirganj':
            case_displays = (WazirganjDisplay(self, self.get_case(case))
                for case in self.es_results['hits'].get('hits', []))
            for disp in case_displays:
                yield [
                    disp.case_name,
                    disp.awc,
                    disp.current_status,
                    disp.month,
                    disp.window,
                    disp.one,
                    disp.two,
                    disp.four,
                    disp.five,
                    disp.cash_to_transferred
                ]

    @property
    def user_filter(self):
        return super(MetReport, self).user_filter