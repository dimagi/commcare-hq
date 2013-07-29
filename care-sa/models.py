from couchforms.models import XFormInstance
import fluff
from corehq.fluff.calculators import xform as xcalculators
from casexml.apps.case.models import CommCareCase
from corehq.apps.fixtures.models import FixtureDataType, FixtureDataItem
from corehq.apps.groups.models import Group

def lookup_province_id_from_form_id(form_id):
    case = CommCareCase.get_by_xform_id(form_id).first()
    fixture_type = FixtureDataType.by_domain_tag('care-ihapc-live',
                                                 'province').first()

    fixture_item = FixtureDataItem.by_field_value(
        'care-ihapc-live',
        fixture_type,
        'id',
        case.province
    ).first()

    return fixture_item.get_id

def lookup_cbo_id_from_form_id(form_id):
    case = CommCareCase.get_by_xform_id(form_id).first()
    group = Group.by_user(case.user_id).one()

    # if the id doesn't belong to a user, maybe its a group?
    if not group:
        group = Group.get(case.user_id)

    return group.get_id

get_user_id = lambda form: form.metadata.userID
get_province = lambda form: lookup_province_id_from_form_id(form.get_id)
get_cbo = lambda form: lookup_cbo_id_from_form_id(form.get_id)

HCT_XMLNS = 'http://openrosa.org/formdesigner/BA7D3B3F-151C-4709-A020-CF79B7F2E876'
HBC_XMLNS = "http://openrosa.org/formdesigner/19A3BDCB-5EE6-4D1B-B64B-79361D7D9885"
PMM_XMLNS = "http://openrosa.org/formdesigner/d234f78e65e30eb72527c1118cf0de15e1181ddc"
IACT_XMLNS = "http://openrosa.org/formdesigner/BE27B9F4-A260-4110-B187-28D572B46DB0"


class CareSAFluff(fluff.IndicatorDocument):
    document_class = XFormInstance

    domains = ('care-ihapc-live',)
    group_by = (
        'domain',
        fluff.AttributeGetter('user_id', get_user_id),
        fluff.AttributeGetter('province', get_province),
        fluff.AttributeGetter('cbo', get_cbo),
    )

    # Report 1
    # Testing and Counseling

    #1a
    # tested
    hiv_counseling = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/testing_consent',
        property_value='counseling_testing',
    )

    #1b
    hiv_tested = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/hiv_tested',
        property_value='yes',
    )

    #1c
    # no results
    internal_hiv_pos_test = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/test_results',
        property_value='hiv_pos',
    )
    hiv_positive = xcalculators.FormANDCalculator(
        [hiv_tested, internal_hiv_pos_test]
    )

    #1d
    new_hiv_tb_screen = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/test_results',
        operator=xcalculators.ANY,
    )

    #1e
    internal_tb_screening = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/tb_screening',
        operator=xcalculators.ANY,
    )
    internal_tested_before = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/tested_b4',
        property_value='yes',
    )
    hiv_known_screened = xcalculators.FormANDCalculator(
        [internal_tb_screening, internal_tested_before]
    )

    #1f
    referred_tb_signs = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/refer_phcf_tb',
        property_value='yes',
    )

    #1g TODO NOT IN FORM

    #1h
    internal_refer_phcf = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/refer_phcf',
        property_value='yes',
    )
    #1ha
    internal_new_patient = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/newly_diagnosed',
        property_value='yes',
    )
    referred_for_cdf_new = xcalculators.FormANDCalculator(
        [internal_refer_phcf, internal_new_patient]
    )
    #1hb
    internal_existing_patient = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/newly_diagnosed',
        property_value='no',
    )
    referred_for_cdf_existing = xcalculators.FormANDCalculator(
        [internal_refer_phcf, internal_existing_patient]
    )

    #1i
    internal_new_cd4 = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/new_cd4',
        property_value='yes',
    )
    new_hiv_cd4_results = xcalculators.FormANDCalculator(
        [internal_new_cd4, internal_new_patient]
    )

    #1k
    internal_refer_hbc = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/refer_hbc',
        property_value='yes',
    )
    internal_refer_iact = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/refer_iact',
        property_value='yes',
    )
    internal_care_referral = xcalculators.FormORCalculator(
        [internal_refer_hbc, internal_refer_iact]
    )
    internal_test_results_yes = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/test_results',
        property_value='yes',
    )
    new_hiv_in_care_program = xcalculators.FormANDCalculator(
        [internal_care_referral, internal_test_results_yes]
    )

    #1l
    individual_tests = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/couple',
        property_value='single',
    )

    #1m
    couple_tests = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HCT_XMLNS,
        property_path='form/couple_number',
        operator=xcalculators.ANY,
    )

    #2a
    deceased = xcalculators.FilteredFormPropertyCalculator(
        xmlns=PMM_XMLNS,
        property_path='form/why_close',
        property_value='deceased',
    )

    #2b TODO
    #lost_to_followup = xcalculators.FilteredFormPropertyCalculator(
        #xmlns=HBC_XMLNS,
        #property_path='form/visit_date',
        #property_value='90',
    #)

    #2c TODO

    #2d
    tb_treatment_completed = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/tb_treatment',
        property_value='completed_treatment',
    )

    #2e TODO

    #2f TODO

    #2g TODO

    #2h
    internal_on_ipt = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/on_ipt',
        property_value='yes',
    )
    new_hiv_starting_ipt = xcalculators.FormANDCalculator(
        [internal_new_patient, internal_on_ipt]
    )

    #2i
    internal_on_bactrim = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/on_bactrim',
        property_value='yes',
    )
    new_hiv_starting_bactrim = xcalculators.FormANDCalculator(
        [internal_new_patient, internal_on_bactrim]
    )

    #2k TODO
    internal_on_arv = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/on_arv',
        property_value='yes',
    )
    internal_pre_art = xcalculators.FilteredFormPropertyCalculator(
        xmlns=HBC_XMLNS,
        property_path='form/pre_art',
        property_value='yes',
    )
    internal_hiv_care = xcalculators.FormORCalculator(
        [
            internal_on_bactrim,
            internal_on_ipt,
            internal_pre_art,
            internal_on_arv
        ]
    )
    #internal_tb_re_screening = xcalculators.FilteredFormPropertyCalculator(

    #hiv_on_care_screened_for_tb = xcalculators.FormANDCalculator(
        #[internal_hiv_care, internal_tb_re_screening]
    #)

    #2l TODO

    #3a
    hiv_pos_enrolled = xcalculators.FilteredFormPropertyCalculator(
        xmlns=IACT_XMLNS,
        property_path='form/first_session',
        property_value='yes',
    )

    #3b
    hiv_pos_completed = xcalculators.FilteredFormPropertyCalculator(
        xmlns=IACT_XMLNS,
        property_path='form/last_session',
        property_value='confirm',
    )

    #3c
    hiv_pos_pipeline = xcalculators.FilteredFormPropertyCalculator(
        xmlns=IACT_XMLNS,
        property_path='form/session_no',
        property_value='session_5',
    )

    #3d TODO CASE

    #3f
    internal_iact_not_complete = xcalculators.FilteredFormPropertyCalculator(
        xmlns=IACT_XMLNS,
        property_path='form/last_session',
        property_value='not_complete',
    )
    iact_participant_ipt = xcalculators.FormANDCalculator(
        [internal_iact_not_complete, internal_on_ipt]
    )

    #3g
    iact_participant_bactrim = xcalculators.FormANDCalculator(
        [internal_iact_not_complete, internal_on_bactrim]
    )

    #3h
    iact_participant_art = xcalculators.FormANDCalculator(
        [internal_iact_not_complete, internal_pre_art]
    )

    #3i
    iact_participant_arv = xcalculators.FormANDCalculator(
        [internal_iact_not_complete, internal_on_arv]
    )

    #3j...n TODO


    class Meta:
        app_label = 'care-sa'

CareSAFluffPillow = CareSAFluff.pillow()
