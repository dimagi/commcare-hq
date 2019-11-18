from django.utils.translation import ugettext as _

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, NumericColumn
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from corehq.apps.reports.standard import MonthYearMixin
from corehq.apps.reports.standard.cases.basic import CaseListReport
from custom.common.filters import RestrictedAsyncLocationFilter
from custom.m4change.reports import validate_report_parameters, get_location_hierarchy_by_id
from custom.m4change.reports.anc_hmis_report import AncHmisReport
from custom.m4change.reports.immunization_hmis_report import ImmunizationHmisReport
from custom.m4change.reports.ld_hmis_report import LdHmisReport
from custom.m4change.reports.reports import M4ChangeReport
from custom.m4change.reports.sql_data import AncHmisCaseSqlData, ImmunizationHmisCaseSqlData, LdHmisCaseSqlData, \
    AllHmisCaseSqlData


def _get_rows(row_data, form_data, key):
    data = form_data.get(key)
    rows = dict([(row_key, data.get(row_key, 0)) for row_key in row_data])
    for key in rows:
        if rows.get(key) == None:
            rows[key] = 0
    rows["antenatal_first_visit_total"] = rows.get("attendance_before_20_weeks_total") \
                                          + rows.get("attendance_after_20_weeks_total")
    rows["hiv_positive_pregnant_women_assessed_for_art_eligibility_clinical_cd4"] = \
        rows.get("assessed_for_clinical_stage_eligibility_total") + rows.get("assessed_for_clinical_cd4_eligibility_total")
    rows["pregnant_positive_women_received_arv_for_pmtct"] = \
        rows.get("pregnant_hiv_positive_women_received_art_total") +\
        rows.get("pregnant_hiv_positive_women_received_arv_total") +\
        rows.get("pregnant_hiv_positive_women_received_azt_total") +\
        rows.get("pregnant_hiv_positive_women_received_mother_sdnvp_total")
    return rows


@location_safe
class AllHmisReport(MonthYearMixin, CaseListReport, M4ChangeReport):
    ajax_pagination = False
    asynchronous = True
    exportable = True
    emailable = False
    name = "Facility ALL HMIS Report"
    slug = "facility_all_hmis_report"
    default_rows = 25
    base_template = "m4change/report.html"
    report_template_path = "m4change/report_content.html"

    fields = [
        RestrictedAsyncLocationFilter,
        MonthFilter,
        YearFilter
    ]

    @classmethod
    def get_report_data(cls, config):
        validate_report_parameters(["domain", "location_id", "datespan"], config)

        domain = config["domain"]
        location_id = config["location_id"]
        datespan = config["datespan"]
        user = config["user"]
        sql_data = [
            AncHmisCaseSqlData(domain=domain, datespan=datespan).data,
            LdHmisCaseSqlData(domain=domain, datespan=datespan).data,
            ImmunizationHmisCaseSqlData(domain=domain, datespan=datespan).data,
            AllHmisCaseSqlData(domain=domain, datespan=datespan).data
        ]
        locations = get_location_hierarchy_by_id(location_id, domain, user)
        row_data = AllHmisReport.get_initial_row_data()

        for data in sql_data:
            for location_id in locations:
                key = (domain, location_id)
                if key in data:
                    report_rows = _get_rows(row_data, data, key)
                    for key in report_rows:
                        row_data.get(key)["value"] += report_rows.get(key)
        return sorted([(key, row_data[key]) for key in row_data], key=lambda t: t[1].get("hmis_code"))

    @classmethod
    def get_initial_row_data(cls):
        all_hmis_report_data = {
            "newborns_low_birth_weight_discharged_total": {
                "hmis_code": 46,
                "label": _("Newborns with low birth weight discharged - Total"),
                "value": 0
            },
            "newborns_low_birth_weight_discharged_male_total": {
                "hmis_code": 46.1,
                "label": _("Newborns with low birth weight discharged - Male"),
                "value": 0
            },
            "newborns_low_birth_weight_discharged_female_total": {
                "hmis_code": 46.2,
                "label": _("Newborns with low birth weight discharged - Female"),
                "value": 0
            },
            "pregnant_mothers_referred_out_total": {
                "hmis_code": 105,
                "label": _("Pregnant Mothers Referred out"),
                "value": 0
            },
            "anc_anemia_test_done_total": {
                "hmis_code": 118,
                "label": _("ANC Anemia test done"),
                "value": 0
            },
            "anc_anemia_test_positive_total": {
                "hmis_code": 119,
                "label": _("ANC Anemia test positive"),
                "value": 0
            },
            "anc_proteinuria_test_done_total": {
                "hmis_code": 120,
                "label": _("ANC Proteinuria Test done"),
                "value": 0
            },
            "anc_proteinuria_test_positive_total": {
                "hmis_code": 121,
                "label": _("ANC Proteinuria test positive"),
                "value": 0
            },
            "hiv_rapid_antibody_test_done_total": {
                "hmis_code": 122,
                "label": _("HIV rapid antibody test done"),
                "value": 0
            },
            "deaths_of_women_related_to_pregnancy_total": {
                "hmis_code": 138,
                "label": _("Deaths of women related to pregnancy"),
                "value": 0
            },
            "pregnant_mothers_tested_for_hiv_total": {
                "hmis_code": 144,
                "label": _("Pregnant mothers tested positive for HIV"),
                "value": 0
            },
            "pregnant_mothers_with_confirmed_malaria_total": {
                "hmis_code": 196,
                "label": _("Pregnant Mothers with confirmed Malaria"),
                "value": 0
            },
            "anc_women_previously_known_hiv_status_total": {
                "hmis_code": 162,
                "label": _("ANC Women with previously known HIV status (at ANC)"),
                "value": 0
            },
            "pregnant_women_received_hiv_counseling_and_result_anc_total": {
                "hmis_code": 163,
                "label": _("Pregnant women who received HIV counseling testing and received result at ANC"),
                "value": 0
            },
            "pregnant_women_received_hiv_counseling_and_result_ld_total": {
                "hmis_code": 164,
                "label": _("Pregnant women who received HIV counseling testing and received result at L&D"),
                "value": 0
            },
            "partners_of_hiv_positive_women_tested_negative_total": {
                "hmis_code": 166,
                "label": _("Partners of HIV positive women who tested HIV negative"),
                "value": 0
            },
            "partners_of_hiv_positive_women_tested_positive_total": {
                "hmis_code": 167,
                "label": _("Partners of HIV positive women who tested positive"),
                "value": 0
            },
            "hiv_positive_pregnant_women_assessed_for_art_eligibility_clinical_cd4": {
                "hmis_code": 170,
                "label": _("HIV positive pregnant women assessed for ART eligibility by either clinical stage or CD4"),
                "value": 0
            },
            "assessed_for_clinical_stage_eligibility_total": {
                "hmis_code": 170.1,
                "label": _("Assessed for clinical stage eligibility"),
                "value": 0
            },
            "assessed_for_clinical_cd4_eligibility_total": {
                "hmis_code": 170.2,
                "label": _("Assessed for cd4-count eligibility"),
                "value": 0
            },
            "pregnant_hiv_positive_women_received_art_total": {
                "hmis_code": 171,
                "label": _("Pregnant HIV positive women who received ART prophylaxis for PMTCT (Triple)"),
                "value": 0
            },
            "pregnant_hiv_positive_women_received_arv_total": {
                "hmis_code": 172,
                "label": _("Pregnant positive women who received ARV prophylaxis (SdNvP in Labor + (AZT + 3TC))"),
                "value": 0
            },
            "pregnant_hiv_positive_women_received_azt_total": {
                "hmis_code": 173,
                "label": _("Pregnant HIV positive woman who received ARV prophylaxis for PMTCT (AZT)"),
                "value": 0
            },
            "pregnant_hiv_positive_women_received_mother_sdnvp_total": {
                "hmis_code": 174,
                "label": _("Pregnant positive women who received ARV prophylaxis for PMTCT(SdNVP in labour only)"),
                "value": 0
            },
            "pregnant_positive_women_received_arv_for_pmtct": {
                "hmis_code": 175,
                "label": _(
                    "Pregant positive woman who received ARV prophylaxis for PMTCT(Total) = (171 + 172 + 173 + 174)"),
                "value": 0
            },
            "infants_hiv_women_cotrimoxazole_lt_2_months_total": {
                "hmis_code": 176,
                "label": _("Infants born to HIV infected women started on contrimoxazole prophylaxis within 2 months"),
                "value": 0
            },
            "infants_hiv_women_cotrimoxazole_gte_2_months_total": {
                "hmis_code": 177,
                "label": _("Infants born to HIV infected women started on cotrimoxazole prophylaxis 2 months & above"),
                "value": 0
            },
            "infants_hiv_women_received_hiv_test_lt_2_months_total": {
                "hmis_code": 178,
                "label": _(
                    "Infants born to HIV infected women who received an HIV test within two months of birth - (DNA -PCR)"),
                "value": 0
            },
            "infants_hiv_women_received_hiv_test_gte_2_months_total": {
                "hmis_code": 179,
                "label": _(
                    "Infants born to HIV infected women who received an HIV test after two months of birth - (DNA - PCR)"),
                "value": 0
            },
            "infants_hiv_women_received_hiv_test_lt_18_months_total": {
                "hmis_code": 180,
                "label": _(
                    "Infants born to HIV infected women who received an HIV test at 18 months - (HIV Rapid test)"),
                "value": 0
            },
            "infants_hiv_women_received_hiv_test_gte_18_months_total": {
                "hmis_code": 181,
                "label": _("Infant born to HIV infected women who tested negative to HIV Rapid test at 18 months"),
                "value": 0
            },
            "hiv_exposed_infants_breast_feeding_receiving_arv_total": {
                "hmis_code": 182,
                "label": _("HIV exposed infants breast feeding and receiving ARV prophylaxis"),
                "value": 0
            }
        }

        return dict(
            list(AncHmisReport.get_initial_row_data().items()) +\
            list(LdHmisReport.get_initial_row_data().items()) +\
            list(ImmunizationHmisReport.get_initial_row_data().items()) +\
            list(all_hmis_report_data.items())
        )

    @property
    def headers(self):
        headers = DataTablesHeader(NumericColumn(_("HMIS code")),
                                   DataTablesColumn(_("Data Point")),
                                   NumericColumn(_("Total")))
        return headers

    @property
    def rows(self):
        row_data = AllHmisReport.get_report_data({
            "location_id": self.request.GET.get("location_id", None),
            "datespan": self.datespan,
            "domain": str(self.domain),
            "user": self.request.couch_user
        })

        for row in row_data:
            yield [
                self.table_cell(row[1].get("hmis_code")),
                self.table_cell(row[1].get("label")),
                self.table_cell(row[1].get("value"))
            ]

    @property
    def rendered_report_title(self):
        return self.name
