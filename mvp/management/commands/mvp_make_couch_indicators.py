from django.core.management.base import LabelCommand, CommandError
from corehq.apps.indicators.models import IndicatorDefinition, CaseDataInFormIndicatorDefinition, \
    FormDataAliasIndicatorDefinition, FormDataInCaseIndicatorDefinition, DynamicIndicatorDefinition, \
    CouchViewIndicatorDefinition, CombinedCouchViewIndicatorDefinition
from mvp.models import MVP, MVPRelatedCaseDataInFormIndicatorDefinition, MVPRelatedCaseDataInCaseIndicatorDefinition, MVPActiveCasesCouchViewIndicatorDefinition

SIMPLE_COUCH_VIEW_INDICATORS = dict(
    under5_child_health=dict(
        num_under5_visits=dict(
            description="No. of Under-5s Visited",
            title="# Under-5s Visited",
            indicator_key="under5"
        ),
        under5_danger_signs=dict(
            description="No. of Under-5s Referred for Danger Signs",
            title="# Under-5s Referred for Danger Signs",
            indicator_key="under5_danger_signs"
        ),
        under5_fever=dict(
            description="No. of Under-5s with uncomplicated Fever",
            title="# Under-5s w/ Uncomplicated Fever",
            indicator_key="under5_fever"
        ),
        under5_fever_rdt=dict(
            description="No. of Under-5s with uncomplicated fever who received RDT test",
            title="# Under-5s w/ Uncomplicated Fever receiving RDT Test",
            indicator_key="under5_fever rdt_test_received"
        ),
        under5_fever_rdt_positive=dict(
            description="No. of Under-5s with uncomplicated fever who received RDT test and were RDT positive",
            title="# Under-5s w/ Positive RDT Result",
            indicator_key="under5_fever rdt_test_received rdt_test_positive"
        ),
        under5_fever_rdt_negative=dict(
            description="No. of Under-5s with negative RDT result",
            title="# Under-5s w/ Negative RDT Result",
            indicator_key="under5_fever rdt_test_negative"
        ),
        under5_fever_rdt_positive_medicated=dict(
            description="No. of Under-5s with positive RDT result who received antimalarial/ADT medication",
            title="# Under-5s w/ Positive RDT Receiving Antimalarial/ADT",
            indicator_key="under5_fever rdt_test_received rdt_test_positive anti_malarial"
        ),
        under5_fever_rdt_negative_medicated=dict(
            description="No. of Under-5s with negative RDT result who received antimalarial/ADT medication",
            title="# Under-5s w/ Negative RDT Receiving Antimalarial/ADT",
            indicator_key="under5_fever rdt_test_negative anti_malarial"
        ),
        under5_fever_rdt_not_received=dict(
            description="No. of Under-5s with uncomplicated fever who did NOT receive RDT "
                        "test due to 'RDT not available' with CHW",
            title="# Under-5s w/ 'RDT not available",
            indicator_key="under5_fever rdt_not_available"
        ),
        under5_diarrhea=dict(
            description="No. of Under-5s with uncomplicated Diarrhea",
            title="# Under-5s w/ Uncomplicated Diarrhea",
            indicator_key="under5_diarrhea"
        ),
        under5_diarrhea_ors=dict(
            description="No. Under-5s with uncomplicated diarrhea who received ORS",
            title="# Under-5s w/ Uncomplicated Diarrhea Receiving ORS",
            indicator_key="under5_diarrhea ors"
        )
    ),
    anc_visits=dict(
        edd_soon_anc4=dict(
            description="No. of Pregnant women reporting at least four (4) Antenatal Care "
                        "visit by 8 months of gestation this time period",
            title="Pregnant receiving 4 ANC visits to facility by 8 months gestation",
            indicator_key="anc4"
        ),
        edd_soon_visit=dict(
            description="No. of Pregnant women who have at least one visit by 8 months of gestation",
            title="Pregnant receiving at least one ANC visit by 8 months gestation",
            indicator_key="visit"
        )
    ),
    child_registrations=dict(
        num_births_registered=dict(
            description="No. of Births Registered",
            title="# Registered Births",
            indicator_key="registration"
        ),
        num_births_registered_in_facility=dict(
            description="No. of Births delivered in a Health Facility during the time period",
            title="# Births delivered in Health Facility",
            indicator_key="facility_delivery"
        )
    ),
    urgent_referrals_by_form=dict(
        num_urgent_referrals=dict(
            description="No. of Urgent Referrals",
            title="# Urgent Referrals",
            indicator_key="urgent_referral"
        )
    ),
    urgent_referrals_by_case=dict(
        urgent_referral_followups=dict(
            description="No. urgent referrals (codes A, E, B) or treatment receiving CHW follow-up within 2 days " \
                        "of referral / treatment during the time period",
            title="# Urgent Referrals w/ Followup within 2 days",
            indicator_key="urgent_referral_followup"
        )
    ),
    family_planning=dict(
        household_num_fp=dict(
            description="No. households using family planning",
            title="# Households Using Family Planning",
            indicator_key="num_fp"
        ),
        household_num_ec=dict(
            description="No. of Households Seen for Family Planning",
            title="# of Women 15-49 Seen for Family Planning",
            indicator_key="num_ec"
        )
    ),
    child_cases_by_dob=dict(
        newborn_visit=dict(
            description="No. of newborns receiving first CHW check-up within 7 days of birth during the time period",
            title="# Newborns checked within 7 days of birth",
            indicator_key="newborn_visit",
            startdate_shift=-7,
        )
    ),
    child_muac=dict(
        child_muac_wasting=dict(
            description="No. children aged 6-59 months with moderate or severe wasting (MUAC < 125)"
                        " at last MUAC reading this time period",
            title="# 6-59 month Children with MUAC < 125",
            indicator_key="muac_wasting"
        ),
        child_muac_reading=dict(
            description="No. children aged 6-59 months with MUAC reading this time period",
            title="# 6-59 month Children with MUAC reading",
            indicator_key="muac_reading"
        ),
        child_muac_routine=dict(
            description="No. of children aged 6-59 months receiving on-time routine (every 90 days)"\
                        " MUAC readings during the time period",
            title="# Under5s receiving on-time MUAC (90 days)",
            indicator_key="routine_muac"
        )
    ),
    visited_households=dict(
        visited_households_past30days=dict(
            description="No. of unique households visited in the last 30 days",
            title="# Households Visited in Last 30 Days",
            indicator_key="visited",
            fixed_datespan_days=30
        ),
        visited_households_past90days=dict(
            description="No. of unique households visited in the last 90 days",
            title="# Households Visited in Last 90 Days",
            indicator_key="visited",
            fixed_datespan_days=90
        )
    ),
    visited_under5=dict(
        under5_visited_past30days=dict(
            description="No. of Under-5s visited in the last 30 days",
            title="# Under-5s Visited in Last 30 Days",
            indicator_key="under5",
            fixed_datespan_days=30
        ),
        neonate_visited_past7days=dict(
            description="No. of Neonate Newborns visited in the last 7 days",
            title="# Newborns Visited in Last 7 Days",
            indicator_key="neonate",
            fixed_datespan_days=7
        )
    ),
    visited_pregnancies=dict(
        pregnant_visited_past30days=dict(
            description="No. of Pregnant Women visited in the last 30 days",
            title="# Pregnant Women Visited in Last 30 Days",
            indicator_key="pregnant",
            fixed_datespan_days=30
        ),
    ),
    households_by_visit_date=dict(
        num_household_visits=dict(
            dscription="No. of Household visits",
            title="# Household Visits",
            indicator_key="visit"
        )
    )
)

ACTIVE_CASES_INDICATORS=dict(
    household_cases_by_status=dict(
        num_active_households_past30days=dict(
            description="No. of Active Households in the last 30 days",
            title="# Active Household Cases in last 30 days",
            indicator_key="",
            fixed_datespan_days=30
        ),
        num_active_households_past90days=dict(
            description="No. of Active Households in the last 90 days",
            title="# Active Household Cases in last 90 days",
            indicator_key="",
            fixed_datespan_days=90
        ),
        num_active_households=dict(
            description="No. of Households",
            indicator_key=""
        )
    ),
    pregnancy_cases_by_status=dict(
        num_active_pregnancies_past30days=dict(
            description="No. of Pregnant Women in the last 30 days",
            title="# Pregnant Women in last 30 days",
            indicator_key="",
            fixed_datespan_days=30,
            startdate_shift=-266
        ),
        num_active_pregnancies=dict(
            description="No. of Pregnant Women",
            title="# Pregnant Women",
            indicator_key="",
            startdate_shift=-266
        )
    ),
    child_cases_by_status=dict(
        num_under5_past30days=dict(
            description="Number of Under-5s in the last 30 days",
            title="# Under-5s in last 30 days",
            indicator_key="",
            fixed_datespan_days=30,
            startdate_shift=-1826, # <60 months (5 years)
        ),
        num_neonate_past7days=dict(
            description="Number of Neonates in the last 7 days",
            title="# Neonates in last 7 days",
            indicator_key="",
            fixed_datespan_days=7,
            startdate_shift=-31,
        ),
        num_newborns=dict(
            description="No. of newborns",
            title="# Newborns",
            indicator_key="",
            startdate_shift=-7,
        ),
        num_children=dict(
            description="No. of children",
            title="# Children",
            indicator_key="",
            startdate_shift=-1826, # <60 months (5 years)
            enddate_shift=-183 # >6 months
        ),
        num_under5=dict(
            description="No. of Under-5s",
            title="# Under-5s",
            indicator_key="",
            startdate_shift=-1826, # <60 months (5 years)
        )
    )
)

COMPOSITE_INDICATORS = dict(
    newborn_visit_proportion=dict(
        description=" Proportion of newborns receiving first CHW check-up within 7 days" \
                    " of birth during the time period",
        title="% Newborns checked within 7 days of birth",
        numerator_slug="newborn_visit",
        denominator_slug="num_newborns"
    ),
    urgent_referrals_proportion=dict(
        description="Proportion of urgent referrals (codes A, E, B) or treatment receiving CHW " \
                    "follow-up within 2 days of referral / treatment during the time period",
        title="% Referred / Treated receiving on-time follow-up (within 2 days)",
        numerator_slug="urgent_referral_followups",
        denominator_slug="num_urgent_referrals"
    ),
    anc4_proportion=dict(
        description="Proportion of Pregnant women reporting at least four (4) Antenatal Care visit " \
                    "by 8 months of gestation this time period",
        title="% of Pregnant receiving 4 ANC visits to facility by 8 months gestation",
        numerator_slug="edd_soon_anc4",
        denominator_slug="edd_soon_visit"
    ),
    family_planning_households=dict(
        description="Proportion of households reporting use of modern family planning method at" \
                    " last visit this time period",
        title="% women 15-49 years old reporting use of modern family planning method",
        numerator_slug="household_num_fp",
        denominator_slug="household_num_ec"
    ),
    facility_births_proportion=dict(
        description="Proportion of Births delivered in a Health Facility during the time period",
        title="% Births delivered in Health Facility",
        numerator_slug="num_births_registered_in_facility",
        denominator_slug="num_births_registered"
    ),
    muac_wasting_proportion=dict(
        description="Proportion of children aged 6-59 months with moderate or severe wasting (MUAC < 125) " \
                    "at last MUAC reading this time period",
        title="% Under-5s with MUAC < 125",
        numerator_slug="child_muac_wasting",
        denominator_slug="child_muac_reading"
    ),
    muac_routine_proportion=dict(
        description="Proportion of children aged 6-59 months receiving on-time routine (every 90 days) MUAC " \
                    "readings during the time period",
        title="% Under-5s receiving on-time MUAC (90 days)",
        numerator_slug="child_muac_routine",
        denominator_slug="num_children"
    ),
    under5_fever_rdt_negative_medicated_proportion=dict(
        description="Proportion of Under-5s with negative RDT result who received antimalarial/ADT medication",
        title="% Under-5s w/ Negative RDT result who received antimalarial/ADT medication",
        numerator_slug="under5_fever_rdt_negative_medicated",
        denominator_slug="under5_fever_rdt_negative"
    ),
    under5_diarrhea_ors_proportion=dict(
        description="Proportion of Under-5s with uncomplicated diarrhea who received ORS",
        title="% Under-5s with uncomplicated diarrhea who received ORS",
        numerator_slug="under5_diarrhea_ors",
        denominator_slug="under5_diarrhea"
    ),
    under5_fever_rdt_proportion=dict(
        description="Proportion of Under-5s with uncomplicated fever who received RDT test",
        title="% Under-5s w/ uncomplicated fever who received RDT test",
        numerator_slug="under5_fever_rdt",
        denominator_slug="under5_fever"
    ),
    under5_fever_rdt_positive_proportion=dict(
        description="Proportion of Under-5s with uncomplicated fever who received RDT test and were RDT positive",
        title="% Under-5s with uncomplicated fever who received RDT test and were RDT positive",
        numerator_slug="under5_fever_rdt_positive",
        denominator_slug="under5_fever_rdt"
    ),
    under5_fever_rdt_positive_medicated_proportion=dict(
        description="Proportion of Under-5s with positive RDT result who received antimalarial/ADT medication",
        title="% Under-5s w/ Positive RDT result who received antimalarial/ADT medication",
        numerator_slug="under5_fever_rdt_positive_medicated",
        denominator_slug="under5_fever_rdt_positive"
    ),
    under5_fever_rdt_not_received_proportion=dict(
        description="Proportion of Under-5s with uncomplicated fever who did NOT receive RDT "
                    "test due to 'RDT not available' with CHW",
        title="% Under-5s w/ RDT Not Available",
        numerator_slug="under5_fever_rdt_not_received",
        denominator_slug="under5_fever"
    ),
    households_routine_visit_past30days=dict(
        description="Proportion of Households receiving on-time routine visit within last 30 DAYS",
        title="% of HHs receiving visit in last 30 DAYS",
        numerator_slug="visited_households_past30days",
        denominator_slug="num_active_households_past30days"
    ),
    households_routine_visit_past90days=dict(
        description="Proportion of Households receiving on-time routine visit within last 90 DAYS",
        title="% of HHs receiving visit in last 90 DAYS",
        numerator_slug="visited_households_past90days",
        denominator_slug="num_active_households_past90days"
    ),
    under5_routine_visit_past30days=dict(
        description="Proportion of Households with an UNDER-5 CHILD receiving on-time routine visit" \
                    " within last 30 DAYS",
        title="% of HHs w/ Under-5 Child receiving visit in last 30 DAYS",
        numerator_slug="under5_visited_past30days",
        denominator_slug="num_under5_past30days"
    ),
    neonate_routine_visit_past7days=dict(
        description="Proportion of Households with a NEONATE (NEWBORN LESS THAN 30 DAYS OLD) receiving on-time" \
                    " routine visit within last 7 DAYS",
        title="% of HHs with a NEONATE receiving visit in last 30 DAYS",
        numerator_slug="neonate_visited_past7days",
        denominator_slug="num_neonate_past7days"
    ),
    pregnant_routine_visit_past30days=dict(
        description="Proportion of Households with a PREGNANT WOMAN receiving on-time routine visit " \
                    "within last 30 DAYS",
        title="% of HHs with a PREGNANT WOMAN receiving visit in last 30 DAYS",
        numerator_slug="pregnant_visited_past30days",
        denominator_slug="num_active_pregnancies_past30days"
    )
)

class Command(LabelCommand):
    help = "Create the indicator definitions necessary to compute MVP Indicators."
    args = ""
    label = ""

    def handle(self, *args, **options):
        all_indicators = DynamicIndicatorDefinition.view("indicators/dynamic_indicator_definitions",
            reduce=False,
            include_docs=True,
            startkey=["namespace domain slug", MVP.NAMESPACE],
            endkey=["namespace domain slug", MVP.NAMESPACE, {}]
        ).all()
        for ind in all_indicators:
            ind.delete()

        for domain in MVP.DOMAINS:
            shared_args=(
                MVP.NAMESPACE,
                domain
                )
            shared_kwargs = dict(
                version=1
            )

            for couch_view, indicator_defs in SIMPLE_COUCH_VIEW_INDICATORS.items():
                for indicator_slug, indicator_kwargs in indicator_defs.items():
                    indicator_kwargs.update(shared_kwargs)
                    indicator_def = CouchViewIndicatorDefinition.update_or_create_unique(
                        *shared_args,
                        slug=indicator_slug,
                        couch_view="mvp/%s" % couch_view,
                        **indicator_kwargs
                    )
                    indicator_def.save()

            for couch_view, indicator_defs in ACTIVE_CASES_INDICATORS.items():
                for indicator_slug, indicator_kwargs in indicator_defs.items():
                    indicator_kwargs.update(shared_kwargs)
                    indicator_def = MVPActiveCasesCouchViewIndicatorDefinition.update_or_create_unique(
                        *shared_args,
                        slug=indicator_slug,
                        couch_view="mvp/%s" % couch_view,
                        **indicator_kwargs
                    )
                    indicator_def.save()

            for indicator_slug, indicator_kwargs in COMPOSITE_INDICATORS.items():
                indicator_kwargs.update(shared_kwargs)
                indicator_def = CombinedCouchViewIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug=indicator_slug,
                    **indicator_kwargs
                )
                indicator_def.save()

