import copy
from django.http.response import HttpResponse
from django.utils.translation import ugettext as _
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard.cases.basic import CaseListReport
from corehq.apps.api.es import CaseES

from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from dimagi.utils.decorators.memoized import memoized
from corehq.elastic import stream_es_query, ES_URLS
from custom.bihar.reports.display import MCHMotherDisplay, MCHChildDisplay
from corehq.util.timezones import utils as tz_utils
import pytz
from custom.bihar.utils import get_all_owner_ids_from_group


class MCHBaseReport(CustomProjectReport, CaseListReport):
    ajax_pagination = True
    asynchronous = True
    exportable = True
    exportable_all = True
    emailable = False
    fix_left_col = True
    report_template_path = "bihar/reports/report.html"
    model = None

    fields = [
        'corehq.apps.reports.filters.select.GroupFilter',
        'corehq.apps.reports.filters.select.SelectOpenCloseFilter',
    ]

    @property
    def case_filter(self):
        group_id = self.request_params.get('group', '')
        filters = []

        if group_id:
            group = Group.get(group_id)
            users_in_group = get_all_owner_ids_from_group(group)
            if users_in_group:
                or_stm = []
                for user_id in users_in_group:
                    or_stm.append({'term': {'owner_id': user_id}})
                filters.append({"or": or_stm})
            else:
                filters.append({'term': {'owner_id': group_id}})

        return {'and': filters} if filters else {}

    @property
    @memoized
    def case_es(self):
        return CaseES(self.domain)

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%d/%m/%Y') if date else ""

    @property
    def get_all_rows(self):
        query_results = stream_es_query(q=self.es_query, es_url=ES_URLS["cases"], size=999999, chunksize=100)
        case_displays = (self.model(self, self.get_case(case))
                 for case in query_results)

        return self.get_cases(case_displays)

    def build_query(self, case_type=None, afilter=None, status=None, owner_ids=None, user_ids=None, search_string=None):

        def _domain_term():
            return {"term": {"domain.exact": self.domain}}

        subterms = [_domain_term(), afilter] if afilter else [_domain_term()]
        if case_type:
            subterms.append({"term": {"type.exact": case_type}})

        if status:
            subterms.append({"term": {"closed": (status == 'closed')}})

        and_block = {'and': subterms} if subterms else {}

        es_query = {
            'query': {
                'filtered': {
                    'query': {"match_all": {}},
                    'filter': and_block
                }
            },
            'sort': self.get_sorting_block(),
            'from': self.pagination.start,
            'size': self.pagination.count,
        }

        return es_query

    @property
    @memoized
    def es_query(self):
        query = self.build_query(case_type=self.case_type, afilter=self.case_filter,
                                 status=self.case_status)
        return query

    @property
    def rows(self):
        case_displays = (self.model(self, self.get_case(case))
                         for case in self.es_results['hits'].get('hits', []))
        return self.get_cases(case_displays)

    @property
    def export_table(self):
        table = super(MCHBaseReport, self).export_table
        #  remove first row from table headers
        table[0][1].pop(0)
        return table


class MotherMCHRegister(MCHBaseReport):
    name = "Mother MCH register"
    slug = "mother_mch_register"
    default_case_type = "cc_bihar_pregnancy"
    model = MCHMotherDisplay

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("CHW Name")),
                                   DataTablesColumn(_("Mother Name"), sortable=False),
                                   DataTablesColumnGroup(
                                       _("Beneficiary Information"),
                                       DataTablesColumn(_("Husband Name"), sortable=False),
                                       DataTablesColumn(_("City/ward/village"), sortable=False),
                                       DataTablesColumn(_("Full address"), sortable=False),
                                       DataTablesColumn(_("MCTS ID"), sortable=False),
                                       DataTablesColumn(_("Mobile number"), sortable=False),
                                       DataTablesColumn(_("Whose Mobile Number"), sortable=False),
                                       DataTablesColumn(_("Mother DOB / AGE"), sortable=False),
                                       DataTablesColumn(_("JSY beneficiary"), sortable=False),
                                       DataTablesColumn(_("Caste"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Provider Information"),
                                       DataTablesColumn(_("ASHA Name"), sortable=False),
                                       DataTablesColumn(_("Asha phone"), sortable=False),
                                       DataTablesColumn(_("AWC Code , AWC name"), sortable=False),
                                       DataTablesColumn(_("AWW name"), sortable=False),
                                       DataTablesColumn(_("AWW phone number"), sortable=False),
                                       DataTablesColumn(_("LMP"), sortable=False),
                                       DataTablesColumn(_("EDD"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("First ANC (within 12 weeks)"),
                                       DataTablesColumn(_("ANC 1 Date"), sortable=False),
                                       DataTablesColumn(_("ANC 1 Blood Pressure"), sortable=False),
                                       DataTablesColumn(_("ANC 1 Weight"), sortable=False),
                                       DataTablesColumn(_("ANC  Hb"), sortable=False),
                                       DataTablesColumn(_("ANC1 completed within 12 weeks? "), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Second ANC (14-26 weeks)"),
                                       DataTablesColumn(_("ANC 2 Date"), sortable=False),
                                       DataTablesColumn(_("ANC 2 Blood Pressure"), sortable=False),
                                       DataTablesColumn(_("ANC 2 Weight"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Third ANC (28-34 weeks)"),
                                       DataTablesColumn(_("ANC 3 Date"), sortable=False),
                                       DataTablesColumn(_("ANC 3 Blood Pressure"), sortable=False),
                                       DataTablesColumn(_("ANC 3 Weight"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Fourth ANC (34 weeks to Delivery)"),
                                       DataTablesColumn(_("ANC 4 Date"), sortable=False),
                                       DataTablesColumn(_("ANC 4 Blood Pressure"), sortable=False),
                                       DataTablesColumn(_("ANC 4 Weight"), sortable=False),
                                       DataTablesColumn(_("TT1 date"), sortable=False),
                                       DataTablesColumn(_("TT2 date"), sortable=False),
                                       DataTablesColumn(_("TT Booster"), sortable=False),
                                       DataTablesColumn(_("Received  date of 100 IFA tablets "), sortable=False),
                                       DataTablesColumn(_("Anemia"), sortable=False),
                                       DataTablesColumn(_("Any complications"), sortable=False),
                                       DataTablesColumn(_("RTI /STI <yes/no>"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Pregnancy Outcome"),
                                       DataTablesColumn(_("Date of delivery"), sortable=False),
                                       DataTablesColumn(
                                           _("Place of delivery (home - SBA/Non-SBA) (Hospital - public/private)"), sortable=False),
                                       DataTablesColumn(_("Nature of delivery"), sortable=False),
                                       DataTablesColumn(_("Complications"), sortable=False),
                                       DataTablesColumn(_("Discharge date"), sortable=False),
                                       DataTablesColumn(_("Received date of JSY benefits"), sortable=False),
                                       DataTablesColumn(_("Abortion type"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Post Delivery Details"),
                                       DataTablesColumn(
                                           _("First PNC visit (within 48 hours / within 7 days/ after 7 days)"), sortable=False),
                                       DataTablesColumn(_("Complications after delivery"), sortable=False),
                                       DataTablesColumn(_("Type of family planning adopted after delivery"), sortable=False),
                                       DataTablesColumn(_("Checked mother and infant immediate after delivery?"), sortable=False),
                                       DataTablesColumn(_("Infant outcome number code"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Child 1 Details"),
                                       DataTablesColumn(_("Name of the child"), sortable=False),
                                       DataTablesColumn(_("Gender"), sortable=False),
                                       DataTablesColumn(_("First weight at birth"), sortable=False),
                                       DataTablesColumn(_("Breastfed within an hour?"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Child 2 Details"),
                                       DataTablesColumn(_("Name of the child"), sortable=False),
                                       DataTablesColumn(_("Gender"), sortable=False),
                                       DataTablesColumn(_("First weight at birth"), sortable=False),
                                       DataTablesColumn(_("Breastfed within an hour?"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Child 3 Details"),
                                       DataTablesColumn(_("Name of the child"), sortable=False),
                                       DataTablesColumn(_("Gender"), sortable=False),
                                       DataTablesColumn(_("First weight at birth"), sortable=False),
                                       DataTablesColumn(_("Breastfed within an hour?"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Child 4 Details"),
                                       DataTablesColumn(_("Name of the child"), sortable=False),
                                       DataTablesColumn(_("Gender"), sortable=False),
                                       DataTablesColumn(_("First weight at birth"), sortable=False),
                                       DataTablesColumn(_("Breastfed within an hour?"), sortable=False),
                                       DataTablesColumn(_("Migrate status "), sortable=False))
        )
        return headers

    @classmethod
    def get_cases(self, case_displays):
        for disp in case_displays:
            yield [
                disp.chw_name,
                disp.mother_name,
                disp.husband_name,
                disp.ward_number,
                disp.village,
                disp.mcts_id,
                disp.mobile_number,
                disp.mobile_number_whose,
                disp.dob_age,
                disp.jsy_beneficiary,
                disp.caste,
                disp.asha_name,
                disp.asha_number,
                disp.awc_code_name,
                disp.aww_name,
                disp.aww_number,
                disp.lmp,
                disp.edd,
                disp.anc_date_1,
                disp.blood_pressure_1,
                disp.weight_1,
                disp.hemoglobin,
                disp.anc_completed,
                disp.anc_date_2,
                disp.blood_pressure_2,
                disp.weight_2,
                disp.anc_date_3,
                disp.blood_pressure_3,
                disp.weight_3,
                disp.anc_date_4,
                disp.blood_pressure_4,
                disp.weight_4,
                disp.tt1_date,
                disp.tt2_date,
                disp.tt_booster,
                disp.ifa_tablets,
                disp.anemia,
                disp.complications,
                disp.rti_sti,
                disp.add,
                disp.home_sba_assist,
                disp.delivery_nature,
                disp.complications,
                disp.discharge_date,
                disp.jsy_money_date,
                disp.abortion_type,
                disp.first_pnc_time,
                disp.delivery_complications,
                disp.family_planning_type,
                disp.all_pnc_on_time,
                disp.num_children,
                disp.case_name_1,
                disp.gender_1,
                disp.first_weight_1,
                disp.breastfed_hour_1,
                disp.case_name_2,
                disp.gender_2,
                disp.first_weight_2,
                disp.breastfed_hour_2,
                disp.case_name_3,
                disp.gender_3,
                disp.first_weight_3,
                disp.breastfed_hour_3,
                disp.case_name_4,
                disp.gender_4,
                disp.first_weight_4,
                disp.breastfed_hour_4,
                disp.status
            ]

    @property
    def fixed_cols_spec(self):
        return dict(num=2, width=350)

class ChildMCHRegister(MCHBaseReport):
    name = "Child MCH register"
    slug = "child_mch_register"
    default_case_type = "cc_bihar_newborn"
    model = MCHChildDisplay

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("CHW Name")),
                                   DataTablesColumn(_("Child Name"), sortable=False),
                                   DataTablesColumn(_("Father and Mother Name"), sortable=False),
                                   DataTablesColumnGroup(
                                       _("Beneficiary Information"),
                                       DataTablesColumn(_("Mother's MCTS ID"), sortable=False),
                                       DataTablesColumn(_("Gender"), sortable=False),
                                       DataTablesColumn(_("City/ward/village"), sortable=False),
                                       DataTablesColumn(_("Address"), sortable=False),
                                       DataTablesColumn(_("Mobile number"), sortable=False),
                                       DataTablesColumn(_("Whose Mobile Number"), sortable=False),
                                       DataTablesColumn(_("DOB / AGE"), sortable=False),
                                       DataTablesColumn(_("Place of delivery (home - SBA/Non-SBA) (Hospital -  public/private)"), sortable=False),
                                       DataTablesColumn(_("Caste"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Provider Information"),
                                       DataTablesColumn(_("ASHA Name"), sortable=False),
                                       DataTablesColumn(_("Asha phone"), sortable=False),
                                       DataTablesColumn(_("AWC Code , AWC name"), sortable=False),
                                       DataTablesColumn(_("AWW name"), sortable=False),
                                       DataTablesColumn(_("AWW phone number"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("At Birth"),
                                       DataTablesColumn(_("BCG"), sortable=False),
                                       DataTablesColumn(_("OPV0"), sortable=False),
                                       DataTablesColumn(_("Hepatitis-Birth dose "), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("At 6 Weeks"),
                                       DataTablesColumn(_("DPT1"), sortable=False),
                                       DataTablesColumn(_("OPV1"), sortable=False),
                                       DataTablesColumn(_("Hepatitis-B1"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("At 10 Weeks"),
                                       DataTablesColumn(_("DPT2"), sortable=False),
                                       DataTablesColumn(_("OPV2"), sortable=False),
                                       DataTablesColumn(_("Hepatitis-B2"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("At 14 Weeks"),
                                       DataTablesColumn(_("DPT3"), sortable=False),
                                       DataTablesColumn(_("OPV3"), sortable=False),
                                       DataTablesColumn(_("Hepatitis-B3"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Between 9-12 Months"),
                                       DataTablesColumn(_("Measles (1st  dose)"), sortable=False)),
                                   DataTablesColumnGroup(
                                       _("Between 16-24 Months"),
                                       DataTablesColumn(
                                           _("Vitamin A dose-1 "), sortable=False),
                                       DataTablesColumn(_("Measles (2nd dose)/ MR Vaccine"))),
                                   DataTablesColumnGroup(
                                       _("After 2 Years"),
                                       DataTablesColumn(_("DPT Booster"), sortable=False),
                                       DataTablesColumn(_("OPV Booster"), sortable=False),
                                       DataTablesColumn(_("Vitamin A dose-2"), sortable=False),
                                       DataTablesColumn(_("Vitamin A dose-3"), sortable=False),
                                       DataTablesColumn(_("JE Vaccine"), sortable=False))
        )
        return headers


    @classmethod
    def get_cases(self, case_displays):
        for disp in case_displays:
            yield [
                disp.chw_name,
                disp.child_name,
                disp.father_mother_name,
                disp.mcts_id,
                disp.gender,
                disp.ward_number,
                disp.village,
                disp.mobile_number,
                disp.mobile_number_whose,
                disp.dob_age,
                disp.home_sba_assist,
                disp.caste,
                disp.asha_name,
                disp.asha_number,
                disp.awc_code_name,
                disp.aww_name,
                disp.aww_number,
                disp.bcg_date,
                disp.opv_0_date,
                disp.hep_b_0_date,
                disp.dpt_1_date,
                disp.opv_1_date,
                disp.hep_b_1_date,
                disp.dpt_2_date,
                disp.opv_2_date,
                disp.hep_b_2_date,
                disp.dpt_3_date,
                disp.opv_3_date,
                disp.hep_b_3_date,
                disp.measles_date,
                disp.vit_a_1_date,
                disp.date_measles_booster,
                disp.dpt_booster_date,
                disp.opv_booster_date,
                disp.vit_a_2_date,
                disp.vit_a_3_date,
                disp.date_je
            ]

    @property
    def fixed_cols_spec(self):
        return dict(num=3, width=450)
