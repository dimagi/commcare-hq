from django.utils.translation import ugettext as _
from corehq.apps.api.es import FullCaseES
from corehq.apps.reports.standard.inspect import CaseListReport

from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DataTablesColumnGroup
from dimagi.utils.decorators.memoized import memoized
from custom.bihar.reports.display import MCHMotherDisplay


class MotherMCHRegister(CustomProjectReport, CaseListReport):
    name = "Mother MCH register"
    slug = "mothermchregister"
    default_case_type = "cc_bihar_pregnancy"
    # exportable = True

    fields = [
        'corehq.apps.reports.fields.GroupField',
        'corehq.apps.reports.fields.SelectOpenCloseField',
    ]

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("CHW Name")),
                                   DataTablesColumnGroup(
                                       _("Beneficiary Information"),
                                       DataTablesColumn(_("Mother Name"), prop_name="mother_name", rotate=-90),
                                       DataTablesColumn(_("Husband Name"), prop_name="husband_name", rotate=-90),
                                       DataTablesColumn(_("City/ward/village"), prop_name="ward_number", rotate=-90),
                                       DataTablesColumn(_("Full address"), prop_name="village", rotate=-90),
                                       DataTablesColumn(_("MCTS ID"), prop_name="mcts_id", rotate=-90),
                                       DataTablesColumn(_("Mobile number"), prop_name="mobile_number", rotate=-90),
                                       DataTablesColumn(_("Whose Mobile Number"), prop_name="mobile_number_whose",
                                                        rotate=-90),
                                       DataTablesColumn(_("Mother DOB / AGE"), prop_name="dob_age", rotate=-90),
                                       DataTablesColumn(_("JSY beneficiary"), prop_name="jsy_beneficiary", rotate=-90),
                                       DataTablesColumn(_("Caste"), prop_name="caste", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Provider Information"),
                                       DataTablesColumn(_("ASHA Name"), prop_name="asha_name", rotate=-90),
                                       DataTablesColumn(_("Asha phone"), prop_name="asha_number", rotate=-90),
                                       DataTablesColumn(_("AWC Code , AWC name"), prop_name="awc_code_name",
                                                        rotate=-90),
                                       DataTablesColumn(_("AWW name"), prop_name="aww_name", rotate=-90),
                                       DataTablesColumn(_("AWW phone number"), prop_name="aww_number", rotate=-90),
                                       DataTablesColumn(_("LMP"), prop_name="lmp", rotate=-90),
                                       DataTablesColumn(_("EDD"), prop_name="edd", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("First ANC (within 12 weeks)"),
                                       DataTablesColumn(_("ANC 1 Date"), prop_name="anc_date_1", rotate=-90),
                                       DataTablesColumn(_("ANC 1 Blood Pressure"), prop_name="blood_pressure_1",
                                                        rotate=-90),
                                       DataTablesColumn(_("ANC 1 Weight"), prop_name="weight_1", rotate=-90),
                                       DataTablesColumn(_("ANC  Hb"), prop_name="hb", rotate=-90),
                                       DataTablesColumn(_("ANC1 completed within 12 weeks? "),
                                                        prop_name="anc_completed", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Second ANC (14-26 weeks)"),
                                       DataTablesColumn(_("ANC 2 Date"), prop_name="anc_date_2", rotate=-90),
                                       DataTablesColumn(_("ANC 2 Blood Pressure"), prop_name="blood_presure_2",
                                                        rotate=-90),
                                       DataTablesColumn(_("ANC 2 Weight"), prop_name="weight_2", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Third ANC (28-34 weeks)"),
                                       DataTablesColumn(_("ANC 3 Date"), prop_name="anc_date_3", rotate=-90),
                                       DataTablesColumn(_("ANC 3 Blood Pressure"), prop_name="blood_pressure_3",
                                                        rotate=-90),
                                       DataTablesColumn(_("ANC 3 Weight"), prop_name="weight_3", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Fourth ANC (34 weeks to Delivery)"),
                                       DataTablesColumn(_("ANC 4 Date"), prop_name="anc_date_4", rotate=-90),
                                       DataTablesColumn(_("ANC 4 Blood Pressure"), prop_name="blood_pressure_4",
                                                        rotate=-90),
                                       DataTablesColumn(_("ANC 4 Weight"), prop_name="weight_4", rotate=-90),
                                       DataTablesColumn(_("TT1 date"), prop_name="tt1_date", rotate=-90),
                                       DataTablesColumn(_("TT2 date"), prop_name="tt2_date", rotate=-90),
                                       DataTablesColumn(_("TT Booster"), prop_name="tt_booster", rotate=-90),
                                       DataTablesColumn(_("Received  date of 100 IFA tablets "),
                                                        prop_name="ifa_tablets", rotate=-90),
                                       DataTablesColumn(_("Anemia"), prop_name="anemia", rotate=-90),
                                       DataTablesColumn(_("Any complications"), prop_name="complications", rotate=-90),
                                       DataTablesColumn(_("RTI /STI <yes/no>"), prop_name="rti_sti", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Pregnancy Outcome"),
                                       DataTablesColumn(_("Date of delivery"), prop_name="add", rotate=-90),
                                       DataTablesColumn(
                                           _("Place of delivery (home - SBA/Non-SBA) (Hospital - public/private)"),
                                           prop_name="home_sba_assist", rotate=-90),
                                       DataTablesColumn(_("Nature of delivery"), prop_name="delivery_nature",
                                                        rotate=-90),
                                       DataTablesColumn(_("Complications"), prop_name="complications", rotate=-90),
                                       DataTablesColumn(_("Discharge date"), prop_name="discharge_date", rotate=-90),
                                       DataTablesColumn(_("Received date of JSY benefits"), prop_name="jsy_money_date",
                                                        rotate=-90),
                                       DataTablesColumn(_("Abortion type"), prop_name="abortion_type", rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Post Delivery Details"),
                                       DataTablesColumn(
                                           _("First PNC visit (within 48 hours / within 7 days/ after 7 days)"),
                                           prop_name="first_pnc_time", rotate=-90),
                                       DataTablesColumn(_("Complications after delivery"),
                                                        prop_name="delivery_complication", rotate=-90),
                                       DataTablesColumn(_("Type of family planning adopted after delivery"),
                                                        prop_name="family_planning_type", rotate=-90),
                                       DataTablesColumn(_("Checked mother and infant immediate after delivery?"),
                                                        prop_name="all_pnc_on_time", rotate=-90),
                                       DataTablesColumn(_("Infant outcome number code"), prop_name="num_children",
                                                        rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Child 1 Details"),
                                       DataTablesColumn(_("Name of the child"), prop_name="case_name_1", rotate=-90),
                                       DataTablesColumn(_("Gender"), prop_name="gender_1", rotate=-90),
                                       DataTablesColumn(_("First weight at birth"), prop_name="first_weight_1",
                                                        rotate=-90),
                                       DataTablesColumn(_("Breastfed within an hour?"), prop_name="breastfed_hour_1",
                                                        rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Child 2 Details"),
                                       DataTablesColumn(_("Name of the child"), prop_name="case_name_2", rotate=-90),
                                       DataTablesColumn(_("Gender"), prop_name="gander_2", rotate=-90),
                                       DataTablesColumn(_("First weight at birth"), prop_name="first_weight_2",
                                                        rotate=-90),
                                       DataTablesColumn(_("Breastfed within an hour?"), prop_name="breastfed_hour_2",
                                                        rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Child 3 Details"),
                                       DataTablesColumn(_("Name of the child"), prop_name="case_name_3", rotate=-90),
                                       DataTablesColumn(_("Gender"), prop_name="gander_3", rotate=-90),
                                       DataTablesColumn(_("First weight at birth"), prop_name="first_weight_3",
                                                        rotate=-90),
                                       DataTablesColumn(_("Breastfed within an hour?"), prop_name="breastfed_hour_3",
                                                        rotate=-90)),
                                   DataTablesColumnGroup(
                                       _("Child 4 Details"),
                                       DataTablesColumn(_("Name of the child"), prop_name="case_name_4", rotate=-90),
                                       DataTablesColumn(_("Gender"), prop_name="gander_4", rotate=-90),
                                       DataTablesColumn(_("First weight at birth"), prop_name="first_weight_4",
                                                        rotate=-90),
                                       DataTablesColumn(_("Breastfed within an hour?"), prop_name="breastfed_hour_4",
                                                        rotate=-90),
                                       DataTablesColumn(_("Migrate status "), prop_name="status", rotate=-90)))
        return headers

    @property
    @memoized
    def case_es(self):
        return FullCaseES(self.domain)

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    def rows(self):
        case_displays = (MCHMotherDisplay(self.get_case(case))
                         for case in self.es_results['hits'].get('hits', []))

        for disp in case_displays:
            yield [
                disp.owner_display,
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
                disp.blood_presure_2,
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
                disp.delivery_complication,
                disp.family_planning_type,
                disp.all_pnc_on_time,
                disp.num_children,
                disp.case_name_1,
                disp.gender_1,
                disp.first_weight_1,
                disp.breastfed_hour_1,
                disp.case_name_2,
                disp.gander_2,
                disp.first_weight_2,
                disp.breastfed_hour_2,
                disp.case_name_3,
                disp.gander_3,
                disp.first_weight_3,
                disp.breastfed_hour_3,
                disp.case_name_4,
                disp.gander_4,
                disp.first_weight_4,
                disp.breastfed_hour_4,
                disp.status
            ]



class ChildMCHRegister(CustomProjectReport, CaseListReport):
    name = "Child MCH register"
    slug = "childmchregister"
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