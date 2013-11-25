from couchforms.models import XFormInstance
import fluff
from corehq.fluff.calculators import xform as xcalculators
from fluff.filters import ANDFilter, NOTFilter
from casexml.apps.case.models import CommCareCase
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.groups.models import Group
from dimagi.utils.decorators.memoized import memoized
from couchdbkit.exceptions import ResourceNotFound

HCT_XMLNS = 'http://openrosa.org/formdesigner/BA7D3B3F-151C-4709-A020-CF79B7F2E876'
HBC_XMLNS = "http://openrosa.org/formdesigner/19A3BDCB-5EE6-4D1B-B64B-79361D7D9885"
PMM_XMLNS = "http://openrosa.org/formdesigner/d234f78e65e30eb72527c1118cf0de15e1181ddc"
IACT_XMLNS = "http://openrosa.org/formdesigner/BE27B9F4-A260-4110-B187-28D572B46DB0"
TB_XMLNS = "http://openrosa.org/formdesigner/9CB2E10D-18BE-4653-AE8F-A75958991D38"


class CareSAForm(XFormInstance):
    @property
    def user_id(self):
        return self.metadata.userID

    @property
    @memoized
    def gender(self):
        return self.care_case.gender.lower()

    @property
    @memoized
    def age_group(self):
        case = self.care_case

        try:
            if hasattr(case, 'patient_age'):
                age = int(case.patient_age)
            else:
                age = int(case.patients_age)
        except (AttributeError, ValueError):
            # catch fun things like no age being found or age not being
            # a number
            return '3'

        if age < 15:
            return '0'
        elif age < 25:
            return '1'
        else:
            return '2'

    @property
    @memoized
    def cbo(self):
        case = self.care_case

        group = Group.by_user(case.user_id).first()

        # if the id doesn't belong to a user, maybe its a group?
        if not group:
            try:
                group = Group.get(case.user_id)
            except ResourceNotFound:
                return None

        return group._id


    @property
    @memoized
    def province(self):
        case = self.care_case

        fixture_type = FixtureDataType.by_domain_tag('care-ihapc-live',
                                                     'province').first()

        fixture_item = FixtureDataItem.by_field_value(
            'care-ihapc-live',
            fixture_type,
            'id',
            case.province
        ).first()

        return fixture_item._id

    @property
    @memoized
    def care_case(self):
        return CommCareCase.get_by_xform_id(self._id).first()

class CareSAFluff(fluff.IndicatorDocument):
    document_class = XFormInstance
    wrapper = CareSAForm

    document_filter = ANDFilter([
        NOTFilter(xcalculators.FormPropertyFilter(xmlns='http://openrosa.org/user-registration')),
        NOTFilter(xcalculators.FormPropertyFilter(xmlns='http://openrosa.org/user/registration')),
        NOTFilter(xcalculators.FormPropertyFilter(xmlns='http://code.javarosa.org/devicereport')),
        xcalculators.CustomFilter(lambda f: f.gender in ['male', 'female']),
        xcalculators.CustomFilter(lambda f: f.cbo),
    ])


    domains = ('care-ihapc-live',)
    group_by = (
        'domain',
        'user_id',
        'province',
        'cbo',
        'age_group',
        'gender',
    )


    # Report 1
    # Testing and Counseling

    #1a
    # tested
    hiv_counseling = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/testing_consent',
        property_value='counseling_testing',
    )

    #1b
    hiv_tested = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/hiv_tested',
        property_value='yes',
    )

    #1c
    # no results
    internal_hiv_pos_test = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/test_results',
        property_value='hiv_pos',
    )
    hiv_positive = xcalculators.and_calc(
        [hiv_tested, internal_hiv_pos_test]
    )

    #1d
    new_hiv_tb_screen = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/test_results',
        operator=xcalculators.ANY,
    )

    #1ea
    tb_screened = xcalculators.filtered_form_calc(
        xmlns=TB_XMLNS,
        property_path='form/tb_screening',
        operator=xcalculators.ANY,
    )

    #1eb
    internal_tb_screening_any = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/tb_screening',
        operator=xcalculators.ANY,
    )
    internal_testing_counseling = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/testing_consent',
        property_value='only_counseling',
    )
    internal_testing_referral = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/testing_consent',
        property_value='only_referral',
    )
    internal_testing_answers = xcalculators.or_calc(
        [internal_testing_counseling, internal_testing_referral]
    )
    hct_screened = xcalculators.and_calc(
        [internal_tb_screening_any, internal_testing_answers]
    )

    #1f
    referred_tb_signs = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/refer_phcf_tb',
        property_value='yes',
    )

    #1g TODO NOT IN FORM

    #1h
    internal_refer_phcf = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/refer_phcf',
        property_value='yes',
    )
    #1ha
    internal_new_patient = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/newly_diagnosed',
        property_value='yes',
    )
    referred_for_cdf_new = xcalculators.and_calc(
        [internal_refer_phcf, internal_new_patient]
    )
    #1hb
    internal_existing_patient = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/newly_diagnosed',
        property_value='no',
    )
    referred_for_cdf_existing = xcalculators.and_calc(
        [internal_refer_phcf, internal_existing_patient]
    )

    #1i
    internal_new_cd4 = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/new_cd4',
        property_value='yes',
    )
    new_hiv_cd4_results = xcalculators.and_calc(
        [internal_new_cd4, internal_new_patient]
    )

    #1k
    internal_refer_hbc = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/refer_hbc',
        property_value='yes',
    )
    internal_refer_iact = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/refer_iact',
        property_value='yes',
    )
    internal_care_referral = xcalculators.or_calc(
        [internal_refer_hbc, internal_refer_iact]
    )
    new_hiv_in_care_program = xcalculators.and_calc(
        [internal_care_referral, internal_hiv_pos_test]
    )

    #1l
    individual_tests = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/couple',
        property_value='single',
    )

    #1m
    couple_tests = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        indicator_calculator=xcalculators.IntegerPropertyReference('form/couple_number'),
    )

    #1n (currently expected to duplicate 1b
    hiv_community = xcalculators.filtered_form_calc(
        xmlns=HCT_XMLNS,
        property_path='form/hiv_tested',
        property_value='yes',
    )

    #2a
    deceased = xcalculators.filtered_form_calc(
        xmlns=PMM_XMLNS,
        property_path='form/why_close',
        property_value='deceased',
    )

    #2b TODO
    #hbc visit date >= today - 90
    #lost_to_followup = xcalculators.filtered_form_calc(
        #xmlns=HBC_XMLNS,
        #property_path='form/visit_date',
        #property_value='90',
    #)

    #2c TODO not in form

    #2d
    tb_treatment_completed = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/tb_treatment',
        property_value='completed_treatment',
    )

    #2e
    #HBC>>visit_intervention = clinical_support and any other response
    received_cbc = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/visit_intervention', # TODO verify this
        operator=xcalculators.ANY,
    )

    #2f
    existing_cbc = xcalculators.and_calc(
        [received_cbc, internal_existing_patient]
    )

    #2g
    new_hiv_cbc = xcalculators.and_calc(
        [received_cbc, internal_new_patient]
    )

    #2h
    internal_on_ipt = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/on_ipt',
        property_value='yes',
    )
    new_hiv_starting_ipt = xcalculators.and_calc(
        [internal_new_patient, internal_on_ipt]
    )

    #2i
    internal_on_bactrim = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/on_bactrim',
        property_value='yes',
    )
    new_hiv_starting_bactrim = xcalculators.and_calc(
        [internal_new_patient, internal_on_bactrim]
    )

    #2k
    internal_on_arv = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/on_arv',
        property_value='yes',
    )
    internal_pre_art = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/pre_art',
        property_value='yes',
    )
    internal_hiv_care = xcalculators.or_calc(
        [
            internal_on_bactrim,
            internal_on_ipt,
            internal_pre_art,
            internal_on_arv
        ]
    )
    internal_tb_re_screening = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        property_path='form/tb_re_screening',
        operator=xcalculators.ANY,
    )

    hiv_on_care_screened_for_tb = xcalculators.and_calc(
        [internal_hiv_care, internal_tb_re_screening]
    )

    #2l
    family_screened = xcalculators.filtered_form_calc(
        xmlns=HBC_XMLNS,
        indicator_calculator=xcalculators.IntegerPropertyReference('form/number_family', lambda x: x-1),
    )

    #2j NOT IN FORM

    #3a
    hiv_pos_enrolled = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/first_session',
        property_value='yes',
    )

    #3b
    hiv_pos_completed = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/last_session',
        property_value='confirm',
    )

    #3c
    hiv_pos_pipeline = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/session_no',
        property_value='session_5',
        operator=xcalculators.IN,
    )

    #3d TODO CASE

    #3f
    internal_iact_not_complete = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/last_session',
        property_value='not_complete',
    )
    internal_iact_ipt = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/on_ipt',
        property_value='yes',
    )
    iact_participant_ipt = xcalculators.and_calc(
        [internal_iact_not_complete, internal_iact_ipt]
    )

    #3g
    internal_iact_bactrim = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/on_bactrim',
        property_value='yes',
    )
    iact_participant_bactrim = xcalculators.and_calc(
        [internal_iact_not_complete, internal_iact_bactrim]
    )

    #3h
    internal_iact_pre_art = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/pre_art',
        property_value='yes',
    )
    iact_participant_art = xcalculators.and_calc(
        [internal_iact_not_complete, internal_iact_pre_art]
    )

    #3i
    internal_iact_arv = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/on_arv',
        property_value='yes',
    )
    iact_participant_arv = xcalculators.and_calc(
        [internal_iact_not_complete, internal_iact_arv]
    )

    #3j
    cd4lt200 = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/cd4_res',
        property_value=(0, 200),
        operator=xcalculators.IN_RANGE,
    )

    #3k
    cd4lt350 = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/cd4_res',
        property_value=(200, 350),
        operator=xcalculators.IN_RANGE,
    )

    #3l
    cd4gt350 = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/cd4_res',
        property_value=(350, float('inf')),
        operator=xcalculators.IN_RANGE,
    )

    #3m
    internal_skipped_cd4 = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/cd4_res',
        operator=xcalculators.SKIPPED,
    )
    internal_first_session = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/first_session',
        property_value='yes',
    )
    unknown_cd4 = xcalculators.and_calc(
        [internal_skipped_cd4, internal_first_session]
    )

    #3n
    iact_support_groups = xcalculators.filtered_form_calc(
        xmlns=IACT_XMLNS,
        property_path='form/session_no',
        property_value=set(['session_1', 'session_2', 'session_3', 'session_4', 'session_5', 'session_6']),
        operator=xcalculators.IN,
    )

    class Meta:
        app_label = 'care_sa'

CareSAFluffPillow = CareSAFluff.pillow()
