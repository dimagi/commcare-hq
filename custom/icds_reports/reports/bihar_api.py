from custom.icds_reports.models.views import BiharDemographicsView
from custom.icds_reports.const import CAS_API_PAGE_SIZE


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
    return limited_demographics_data,  demographics_data_query.count()
