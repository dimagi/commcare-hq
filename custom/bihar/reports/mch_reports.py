from django.utils.translation import ugettext as _
from corehq.apps.api.es import FullCaseES
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard.inspect import CaseListReport

from corehq.apps.reports.standard import CustomProjectReport, ProjectReportParametersMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from dimagi.utils.decorators.memoized import memoized
from custom.bihar.reports.display import MCHMotherDisplay


class MotherMCHRegister(CustomProjectReport, CaseListReport):
    name = "Mother MCH register"
    slug = "mother_mch_register"
    default_case_type = "cc_bihar_pregnancy"
    ajax_pagination = True
    asynchronous = True
    # is_cacheable = True
    # exportable = True
    emailable = False

    fields = [
        'corehq.apps.reports.fields.GroupField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    ]

    @property
    @memoized
    def case_es(self):
        return FullCaseES(self.domain)

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    def user_filter(self):
        return super(MotherMCHRegister, self).user_filter

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("CHW Name")),
                                   DataTablesColumnGroup(
                                       _("Beneficiary Information"),
                                       DataTablesColumn(_("Mother Name")),
                                       DataTablesColumn(_("Husband Name")),
                                       DataTablesColumn(_("City/ward/village")),
                                       DataTablesColumn(_("Full address")),
                                       DataTablesColumn(_("MCTS ID")),
                                       DataTablesColumn(_("Mobile number")),
                                       DataTablesColumn(_("Whose Mobile Number")),
                                       DataTablesColumn(_("Mother DOB / AGE")),
                                       DataTablesColumn(_("JSY beneficiary")),
                                       DataTablesColumn(_("Caste"))),
                                   DataTablesColumnGroup(
                                       _("Provider Information"),
                                       DataTablesColumn(_("ASHA Name")),
                                       DataTablesColumn(_("Asha phone")),
                                       DataTablesColumn(_("AWC Code , AWC name")),
                                       DataTablesColumn(_("AWW name")),
                                       DataTablesColumn(_("AWW phone number")),
                                       DataTablesColumn(_("LMP")),
                                       DataTablesColumn(_("EDD"))),
                                   DataTablesColumnGroup(
                                       _("First ANC (within 12 weeks)"),
                                       DataTablesColumn(_("ANC 1 Date")),
                                       DataTablesColumn(_("ANC 1 Blood Pressure")),
                                       DataTablesColumn(_("ANC 1 Weight")),
                                       DataTablesColumn(_("ANC  Hb")),
                                       DataTablesColumn(_("ANC1 completed within 12 weeks? "))),
                                   DataTablesColumnGroup(
                                       _("Second ANC (14-26 weeks)"),
                                       DataTablesColumn(_("ANC 2 Date")),
                                       DataTablesColumn(_("ANC 2 Blood Pressure")),
                                       DataTablesColumn(_("ANC 2 Weight"))),
                                   DataTablesColumnGroup(
                                       _("Third ANC (28-34 weeks)"),
                                       DataTablesColumn(_("ANC 3 Date")),
                                       DataTablesColumn(_("ANC 3 Blood Pressure")),
                                       DataTablesColumn(_("ANC 3 Weight"))),
                                   DataTablesColumnGroup(
                                       _("Fourth ANC (34 weeks to Delivery)"),
                                       DataTablesColumn(_("ANC 4 Date")),
                                       DataTablesColumn(_("ANC 4 Blood Pressure")),
                                       DataTablesColumn(_("ANC 4 Weight")),
                                       DataTablesColumn(_("TT1 date")),
                                       DataTablesColumn(_("TT2 date")),
                                       DataTablesColumn(_("TT Booster")),
                                       DataTablesColumn(_("Received  date of 100 IFA tablets ")),
                                       DataTablesColumn(_("Anemia")),
                                       DataTablesColumn(_("Any complications")),
                                       DataTablesColumn(_("RTI /STI <yes/no>"))),
                                   DataTablesColumnGroup(
                                       _("Pregnancy Outcome"),
                                       DataTablesColumn(_("Date of delivery")),
                                       DataTablesColumn(
                                           _("Place of delivery (home - SBA/Non-SBA) (Hospital - public/private)")),
                                       DataTablesColumn(_("Nature of delivery")),
                                       DataTablesColumn(_("Complications")),
                                       DataTablesColumn(_("Discharge date")),
                                       DataTablesColumn(_("Received date of JSY benefits")),
                                       DataTablesColumn(_("Abortion type"))),
                                   DataTablesColumnGroup(
                                       _("Post Delivery Details"),
                                       DataTablesColumn(
                                           _("First PNC visit (within 48 hours / within 7 days/ after 7 days)")),
                                       DataTablesColumn(_("Complications after delivery")),
                                       DataTablesColumn(_("Type of family planning adopted after delivery")),
                                       DataTablesColumn(_("Checked mother and infant immediate after delivery?")),
                                       DataTablesColumn(_("Infant outcome number code"))),
                                   DataTablesColumnGroup(
                                       _("Child 1 Details"),
                                       DataTablesColumn(_("Name of the child")),
                                       DataTablesColumn(_("Gender")),
                                       DataTablesColumn(_("First weight at birth")),
                                       DataTablesColumn(_("Breastfed within an hour?"))),
                                   DataTablesColumnGroup(
                                       _("Child 2 Details"),
                                       DataTablesColumn(_("Name of the child")),
                                       DataTablesColumn(_("Gender")),
                                       DataTablesColumn(_("First weight at birth")),
                                       DataTablesColumn(_("Breastfed within an hour?"))),
                                   DataTablesColumnGroup(
                                       _("Child 3 Details"),
                                       DataTablesColumn(_("Name of the child")),
                                       DataTablesColumn(_("Gender")),
                                       DataTablesColumn(_("First weight at birth")),
                                       DataTablesColumn(_("Breastfed within an hour?"))),
                                   DataTablesColumnGroup(
                                       _("Child 4 Details"),
                                       DataTablesColumn(_("Name of the child")),
                                       DataTablesColumn(_("Gender")),
                                       DataTablesColumn(_("First weight at birth")),
                                       DataTablesColumn(_("Breastfed within an hour?")),
                                       DataTablesColumn(_("Migrate status ")))
        )
        return headers

    @property
    def rows(self):
        case_displays = (MCHMotherDisplay(self, self.get_case(case))
                         for case in self.es_results['hits'].get('hits', []))

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


class ChildMCHRegister(CustomProjectReport, CaseListReport):
    name = "Child MCH register"
    slug = "child_mch_register"
    default_case_type = "cc_bihar_newborn"
    # exportable = True

    fields = [
        'corehq.apps.reports.fields.GroupField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    ]

    @property
    @memoized
    def case_es(self):
        return FullCaseES(self.domain)

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    def data(self):
        return [""]