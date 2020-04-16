from custom.icds_reports.models.views import BiharDemographicsView
from custom.icds_reports.models.aggregate import BiharAPIMotherDetails
from custom.icds_reports.const import CAS_API_PAGE_SIZE
from custom.icds_reports.cache import icds_quickcache


# cache for 2 hours because it wont change atleast for 24 hours.
# This API will be hit in a loop of something and they should be able to scrape all
# the records in 2 hours.
@icds_quickcache(['model_classname', 'month', 'state_id'], timeout=60 * 60 * 2)
def get_total_records_count(model_classname, month, state_id):
    classes = {
        BiharDemographicsView.__name__: BiharDemographicsView,
        BiharAPIMotherDetails.__name__: BiharAPIMotherDetails
    }
    return classes[model_classname].objects.filter(
        month=month,
        state_id=state_id
    ).count()


def get_api_demographics_data(month, state_id, last_person_case_id):
    demographics_data_query = BiharDemographicsView.objects.filter(
        month=month,
        state_id=state_id,
        person_id__gt=last_person_case_id
    ).order_by('person_id').values(
        'state_name',
        'state_site_code',
        'district_name',
        'district_site_code',
        'block_name',
        'block_site_code',
        'supervisor_name',
        'supervisor_site_code',
        'awc_name',
        'awc_site_code',
        'ward_number',
        'household_id',
        'household_name',
        'hh_reg_date',
        'hh_num',
        'hh_gps_location',
        'hh_caste',
        'hh_bpl_apl',
        'hh_minority',
        'hh_religion',
        'hh_member_number',
        'person_id',
        'person_name',
        'has_adhaar',
        'bank_account_number',
        'ifsc_code',
        'age_at_reg',
        'dob',
        'gender',
        'blood_group',
        'disabled',
        'disability_type',
        'referral_status',
        'migration_status',
        'resident',
        'registered_status',
        'rch_id',
        'mcts_id',
        'phone_number',
        'date_death',
        'site_death',
        'closed_on',
        'reason_closure'
    )

    # To apply pagination on database query with data size length
    limited_demographics_data = list(demographics_data_query[:CAS_API_PAGE_SIZE])
    return limited_demographics_data, get_total_records_count(BiharDemographicsView.__name__, month, state_id)


def get_mother_details(month, state_id, last_ccs_case_id):
    bihar_mother_details = BiharAPIMotherDetails.objects.filter(
        month=month,
        state_id=state_id,
        ccs_case_id__gt=last_ccs_case_id
    ).order_by('ccs_case_id').values(
        'household_id',
        'ccs_case_id',
        'person_id',
        'married',
        'husband_name',
        'husband_id',
        'last_preg_year',
        'last_preg_tt',
        'is_pregnant',
        'preg_reg_date',
        'tt_1',
        'tt_2',
        'tt_booster',
        'add',
        'hb'
    )
    limited_mother_details_data = list(bihar_mother_details[:CAS_API_PAGE_SIZE])
    return limited_mother_details_data, get_total_records_count(BiharAPIMotherDetails.__name__, month, state_id)
