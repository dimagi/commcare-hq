from datetime import timedelta
from corehq.apps.change_feed import topics
from corehq.fluff.calculators.xform import IntegerPropertyReference, FormPropertyFilter
from couchforms.models import XFormInstance
import fluff
from corehq.fluff.calculators import xform as xcalculators
from fluff.filters import NOTFilter, ANDFilter, ORFilter
from fluff.models import SimpleCalculator

ADULT_REGISTRATION_XMLNS = 'http://openrosa.org/formdesigner/35af30a99b8343e4dc6f15fe3a7c61d3207fa8e2'
ADULT_FOLLOWUP_XMLNS = 'http://openrosa.org/formdesigner/af5f05c6c5389959335491450381219523e4eaff'
NEWBORN_REGISTRATION_XMLNS = 'http://openrosa.org/formdesigner/2E5C67B9-041A-413C-9F03-4243ED502016'
NEWBORN_FOLLOWUP_XMLNS = 'http://openrosa.org/formdesigner/A4BCDED3-5D58-4312-AF6A-76A97C9530DB'
CHILD_REGISTRATION_XMLNS = 'http://openrosa.org/formdesigner/1DB6E1EF-AEE4-47BF-A13C-1B6CD79E8199'
CHILD_FOLLOWUP_XMLNS = 'http://openrosa.org/formdesigner/d2401a55c30432c0881f8a2f7eaa179338253051'
WEEKLY_SUMMARY_XMLNS = 'http://openrosa.org/formdesigner/7EFB54F1-337B-42A7-9C6A-460AE8B0CDD8'

get_user_id = lambda form: form.metadata.userID

def _filtered_calc_alias(xmlns=None, property_path=None, property_value=None,
                         operator=xcalculators.EQUAL, indicator_calculator=None,
                         window=timedelta(days=1)):
    filter = FormPropertyFilter(xmlns=xmlns, property_path=property_path,
                                property_value=property_value,
                                operator=operator)

    return SimpleCalculator(
        date_provider=xcalculators.default_date,
        filter=filter,
        indicator_calculator=indicator_calculator,
        window=window
    )

def _or_alias(calculators):
    return SimpleCalculator(
        date_provider=xcalculators.default_date,
        filter=ORFilter([calc._filter for calc in calculators if calc._filter]),
        window=timedelta(days=1)
    )

def _and_alias(calculators):
    return SimpleCalculator(
        date_provider=xcalculators.default_date,
        filter=ANDFilter([calc._filter for calc in calculators if calc._filter]),
        window=timedelta(days=1)
    )


class MalariaConsortiumFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    kafka_topic = topics.FORM

    domains = ('mc-inscale',)
    group_by = ('domain', fluff.AttributeGetter('user_id', get_user_id))

    document_filter = ANDFilter([
        NOTFilter(xcalculators.FormPropertyFilter(xmlns='http://openrosa.org/user-registration')),
        NOTFilter(xcalculators.FormPropertyFilter(xmlns='http://code.javarosa.org/devicereport')),
    ])

    # report 1a, district - monthly

    # home visits
    home_visits_adult_reg = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
    )
    home_visits_pregnant = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/pregnant',
        property_value='1',
    )
    home_visits_non_pregnant = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/pregnant',
        property_value='0',
    )
    home_visits_postpartem = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/post_partum',
        property_value='1',
    )
    home_visits_non_postpartem = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/post_partum',
        property_value='0',
    )
    home_visits_male_reg = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/sex',
        property_value='1',
    )
    home_visits_newborn_reg = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
    )
    home_visits_newborn_followup = _filtered_calc_alias(
        xmlns=NEWBORN_FOLLOWUP_XMLNS,
    )
    home_visits_newborn = _or_alias(
        [home_visits_newborn_reg, home_visits_newborn_followup]
    )
    home_visits_child_reg = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
    )
    home_visits_child_followup = _filtered_calc_alias(
        xmlns=CHILD_FOLLOWUP_XMLNS,
    )
    home_visits_children = _or_alias(
        [home_visits_child_reg, home_visits_child_followup]
    )
    home_visits_other_women = _and_alias(
        [home_visits_non_pregnant, home_visits_non_postpartem]
    )
    home_visits_adult_followup = _filtered_calc_alias(
        xmlns=ADULT_FOLLOWUP_XMLNS,
    )
    home_visits_adult = _or_alias(
        [home_visits_adult_reg, home_visits_adult_followup]
    )
    home_visits_followup = _or_alias(
        [home_visits_newborn_followup, home_visits_child_followup, home_visits_adult_followup]
    )
    home_visits_other = _or_alias(
        [home_visits_other_women, home_visits_male_reg, home_visits_adult_followup]
    )
    home_visits_total = _or_alias(
        [home_visits_pregnant, home_visits_postpartem, home_visits_newborn, home_visits_children, home_visits_other]
    )

    # rdt
    rdt_positive_children = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/consult/results_rdt',
        property_value='1',
    )
    rdt_positive_adults = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/rdt_result',
        property_value='1',
    )
    internal_rdt_negative_children = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/consult/results_rdt',
        property_value=set(['2', '3']),
        operator=xcalculators.IN,
    )
    internal_rdt_negative_adults = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/rdt_result',
        property_value=set(['2', '3']),
        operator=xcalculators.IN,
    )
    rdt_others = _or_alias(
         [internal_rdt_negative_adults, internal_rdt_negative_children]
    )
    rdt_total = _or_alias(
        [rdt_positive_children, rdt_positive_adults, rdt_others]
    )

    # diagnosed cases
    diagnosed_malaria_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/diagnosis_given',
        property_value='1',
        operator=xcalculators.IN_MULTISELECT,
    )
    diagnosed_malaria_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/diagnosis_given',
        property_value='1',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_diagnosed_diarrhea_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/diagnosis_given',
        property_value='2',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_diagnosed_diarrhea_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/diagnosis_given',
        property_value='2',
        operator=xcalculators.IN_MULTISELECT,
    )
    diagnosed_diarrhea = _or_alias(
         [internal_diagnosed_diarrhea_child, internal_diagnosed_diarrhea_adult]
    )
    # ari = acute resperatory infection
    internal_diagnosed_ari_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/diagnosis_given',
        property_value='3',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_diagnosed_ari_adult  = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/diagnosis_given',
        property_value='pneumonia',
        operator=xcalculators.IN_MULTISELECT,
    )
    diagnosed_ari = _or_alias(
         [internal_diagnosed_ari_child, internal_diagnosed_ari_adult]
    )
    diagnosed_total = _or_alias(
        [diagnosed_malaria_child, diagnosed_malaria_adult, diagnosed_diarrhea, diagnosed_ari]
    )

    # treated cases
    internal_treated_malaria_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/treatment_given',
        property_value=set(['4', '5', '7', '8', '9', '10', '11']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_diagnosed_and_treated_malaria_child = _and_alias(
        [diagnosed_malaria_child, internal_treated_malaria_child]
    )
    internal_treated_malaria_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/treatment_given',
        property_value=set(['4', '5', '7', '8', '9', '10', '11']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_diagnosed_and_treated_malaria_adult = _and_alias(
        [diagnosed_malaria_adult, internal_treated_malaria_adult]
    )
    treated_malaria = _or_alias(
         [internal_diagnosed_and_treated_malaria_child, internal_diagnosed_and_treated_malaria_adult]
    )
    internal_treated_diarrhea_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/treatment_given',
        property_value='3',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_diagnosed_and_treated_diarrhea_child = _and_alias(
         [internal_diagnosed_diarrhea_child, internal_treated_diarrhea_child]
    )
    internal_treated_diarrhea_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/treatment_given',
        property_value=set(['3', '6']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_diagnosed_and_treated_diarrhea_adult = _and_alias(
         [internal_diagnosed_diarrhea_adult, internal_treated_diarrhea_adult]
    )
    treated_diarrhea = _or_alias(
         [internal_diagnosed_and_treated_diarrhea_child, internal_diagnosed_and_treated_diarrhea_adult]
    )
    internal_treated_ari_child= _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/treatment_given',
        property_value=set(['1', '2']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_diagnosed_and_treated_ari_child = _and_alias(
         [internal_diagnosed_ari_child, internal_treated_ari_child]
    )
    internal_treated_ari_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/treatment_given',
        property_value=set(['1', '2']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_diagnosed_and_treated_ari_adult = _and_alias(
         [internal_diagnosed_ari_adult, internal_treated_ari_adult]
    )
    treated_ari = _or_alias(
        [internal_diagnosed_and_treated_ari_child, internal_diagnosed_and_treated_ari_adult]
    )
    treated_total = _or_alias(
        [treated_malaria, treated_diarrhea, treated_ari]
    )

    # transfers
    internal_transfer_malnutrition_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='5',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_malnutrition_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='5',
        operator=xcalculators.IN_MULTISELECT,
    )
    transfer_malnutrition = _or_alias(
        [internal_transfer_malnutrition_child, internal_transfer_malnutrition_adult]
    )
    internal_transfer_incomplete_vaccination_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='3',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_incomplete_vaccination_newborn = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='3',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_incomplete_vaccination_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='3',
        operator=xcalculators.IN_MULTISELECT,
    )
    transfer_incomplete_vaccination = _or_alias([
        internal_transfer_incomplete_vaccination_child,
        internal_transfer_incomplete_vaccination_newborn,
        internal_transfer_incomplete_vaccination_adult,
    ])
    internal_transfer_danger_signs_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='1',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_danger_signs_newborn = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='1',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_danger_signs_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='1',
        operator=xcalculators.IN_MULTISELECT,
    )
    transfer_danger_signs = _or_alias([
        internal_transfer_danger_signs_child,
        internal_transfer_danger_signs_newborn,
        internal_transfer_danger_signs_adult,
    ])
    transfer_prenatal_consult =  _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='6',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_missing_malaria_meds_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='7',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_transfer_missing_malaria_meds_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='7',
        operator=xcalculators.IN_MULTISELECT,
    )
    transfer_missing_malaria_meds = _or_alias([
        internal_transfer_missing_malaria_meds_child,
        internal_transfer_missing_malaria_meds_adult,
    ])
    internal_transfer_other_child = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value=set(['0', '6']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_transfer_other_newborn = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value=set(['0', '2', '4']),
        operator=xcalculators.ANY_IN_MULTISELECT,
    )
    internal_transfer_other_adult = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='0',
        operator=xcalculators.IN_MULTISELECT,
    )
    transfer_other = _or_alias([
        internal_transfer_other_child,
        internal_transfer_other_newborn,
        internal_transfer_other_adult,
    ])
    transfer_total = _or_alias([
        transfer_malnutrition,
        transfer_incomplete_vaccination,
        transfer_danger_signs,
        transfer_prenatal_consult,
        transfer_missing_malaria_meds,
        transfer_other,
    ])

    # deaths
    deaths_newborn = _filtered_calc_alias(
        xmlns=WEEKLY_SUMMARY_XMLNS,
        indicator_calculator=IntegerPropertyReference('form/deaths/deaths_newborns'),
    )
    deaths_children = _filtered_calc_alias(
        xmlns=WEEKLY_SUMMARY_XMLNS,
        indicator_calculator=IntegerPropertyReference('form/deaths/deaths_children'),
    )
    deaths_mothers = _filtered_calc_alias(
        xmlns=WEEKLY_SUMMARY_XMLNS,
        indicator_calculator=IntegerPropertyReference('form/deaths/deaths_mothers'),
    )
    deaths_other = _filtered_calc_alias(
        xmlns=WEEKLY_SUMMARY_XMLNS,
        indicator_calculator=IntegerPropertyReference('form/deaths/deaths_others'),
    )
    deaths_total = xcalculators.FormSUMCalculator([
        deaths_newborn, deaths_children, deaths_mothers, deaths_other
    ])
    heath_ed_talks = _filtered_calc_alias(
        xmlns=WEEKLY_SUMMARY_XMLNS,
        indicator_calculator=IntegerPropertyReference('form/he/he_number'),
    )
    heath_ed_participants = _filtered_calc_alias(
        xmlns=WEEKLY_SUMMARY_XMLNS,
        indicator_calculator=IntegerPropertyReference('form/he/he_number_participants'),
    )

    # validation of diagnosis and treatment
    internal_child_has_pneumonia = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/has_pneumonia',
        property_value='yes',
    )
    internal_child_diagnosed_pneumonia = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/pneumonia_ds',
        property_value='yes',
    )
    internal_child_given_correct_pneumonia_treatment_1 = _and_alias([
         internal_child_has_pneumonia, internal_treated_ari_child
    ])
    internal_child_given_correct_pneumonia_treatment_2 = _and_alias([
         internal_child_diagnosed_pneumonia, internal_treated_ari_child
    ])

    patients_given_pneumonia_meds_denom = _or_alias([
        internal_child_has_pneumonia,
        internal_child_diagnosed_pneumonia,
        internal_diagnosed_ari_adult,
    ])
    patients_given_pneumonia_meds_num = _or_alias([
        internal_child_given_correct_pneumonia_treatment_1,
        internal_child_given_correct_pneumonia_treatment_2,
        internal_diagnosed_and_treated_ari_adult,
    ])

    internal_child_has_diarrhoea_ds = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/diarrhoea_ds',
        property_value='yes',
    )
    internal_child_has_diarrhoea_symptom = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/non_severe_symptoms/diarrhoea',
        property_value='1',
    )
    internal_child_has_diarrhoea = _or_alias([
        internal_child_has_diarrhoea_ds,
        internal_child_has_diarrhoea_symptom,
    ])
    internal_child_given_correct_diarrhoea_treatment = _and_alias([
        internal_child_has_diarrhoea,
        internal_treated_diarrhea_child,
    ])
    patients_given_diarrhoea_meds_denom = _or_alias([
        internal_child_has_diarrhoea,
        internal_diagnosed_diarrhea_adult,
    ])
    patients_given_diarrhoea_meds_num = _or_alias([
        internal_child_given_correct_diarrhoea_treatment,
        internal_diagnosed_and_treated_diarrhea_adult,
    ])

    internal_child_has_malaria = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/has_malaria',
        property_value='yes',
    )
    internal_child_given_correct_malaria_treatment = _and_alias([
        internal_child_has_malaria,
        internal_treated_malaria_child,
    ])
    patients_given_malaria_meds_denom = _or_alias([
        internal_child_has_malaria,
        diagnosed_malaria_adult,
    ])
    patients_given_malaria_meds_num = _or_alias([
        internal_child_given_correct_malaria_treatment,
        internal_diagnosed_and_treated_malaria_adult,
    ])

    # referrals
    internal_newborn_referral_needed = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/referral_needed',
        property_value='yes',
    )
    internal_newborn_referral_given = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/referral_given',
        property_value='yes',
    )
    internal_newborn_referred_correctly = _and_alias([
        internal_newborn_referral_needed,
        internal_newborn_referral_given
    ])
    internal_child_referral_needed = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/referral_needed',
        property_value='yes',
    )
    internal_child_referral_given = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given',
        property_value='1',
    )
    internal_child_referred_correctly = _and_alias([
        internal_child_referral_needed,
        internal_child_referral_given
    ])
    internal_adult_referral_needed = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/preg_danger_signs/treatment_preg_ds',
        property_value='OK',
    )
    internal_adult_referral_given = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given',
        property_value='1',
    )
    internal_adult_referred_correctly = _and_alias([
        internal_adult_referral_needed,
        internal_adult_referral_given
    ])
    patients_correctly_referred_denom = _or_alias([
        internal_newborn_referral_needed,
        internal_child_referral_needed,
        internal_adult_referral_needed,
    ])
    patients_correctly_referred_num = _or_alias([
        internal_newborn_referred_correctly,
        internal_child_referred_correctly,
        internal_adult_referred_correctly,
    ])

    cases_rdt_not_done = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/consult/results_rdt',
        property_value='0',
    )

    # danger signs not referred
    internal_newborn_has_danger_sign = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/has_danger_sign',
        property_value='yes',
    )
    internal_newborn_referral_not_reported = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_reported',
        property_value='0',
    )
    internal_newborn_referral_reported = _filtered_calc_alias(
        xmlns=NEWBORN_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_reported',
        property_value='1',
    )
    internal_newborn_danger_sign_handled_wrong = _and_alias([
        internal_newborn_has_danger_sign,
        internal_newborn_referral_not_reported,
    ])
    internal_child_has_danger_sign = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/has_danger_sign',
        property_value='yes',
    )
    internal_child_referral_not_given = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given',
        property_value='0',
    )
    internal_child_danger_sign_handled_wrong = _and_alias([
        internal_child_has_danger_sign,
        internal_child_referral_not_given,
    ])
    internal_adult_referral_not_given = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given',
        property_value='0',
    )
    internal_adult_danger_sign_handled_wrong = _and_alias([
        internal_adult_referral_needed,
        internal_adult_referral_not_given,
    ])
    cases_danger_signs_not_referred = _or_alias([
        internal_newborn_danger_sign_handled_wrong,
        internal_child_danger_sign_handled_wrong,
        internal_adult_danger_sign_handled_wrong,
    ])

    # missing malaria meds
    internal_child_no_malaria_meds = _filtered_calc_alias(
        xmlns=CHILD_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='7',
        operator=xcalculators.IN_MULTISELECT,
    )
    internal_adult_no_malaria_meds = _filtered_calc_alias(
        xmlns=ADULT_REGISTRATION_XMLNS,
        property_path='form/self_report/referral_given_reason',
        property_value='7',
        operator=xcalculators.IN_MULTISELECT,
    )
    cases_no_malaria_meds = _or_alias([
        internal_child_no_malaria_meds,
        internal_adult_no_malaria_meds,
    ])
    cases_transferred = _or_alias([
        internal_newborn_referral_reported,
        internal_child_referral_given,
        internal_adult_referral_given,
    ])

    class Meta:
        app_label = 'mc'


MalariaConsortiumFluffPillow = MalariaConsortiumFluff.pillow()
