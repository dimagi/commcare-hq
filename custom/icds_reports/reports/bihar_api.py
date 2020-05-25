from custom.icds_reports.models.views import BiharDemographicsView, BiharVaccineView, BiharAPIMotherView
from custom.icds_reports.const import CAS_API_PAGE_SIZE
from custom.icds_reports.cache import icds_quickcache
from dateutil.relativedelta import relativedelta
from dimagi.utils.dates import force_to_date

# cache for 2 hours because it wont change atleast for 24 hours.
# This API will be hit in a loop of something and they should be able to scrape all
# the records in 2 hours.
@icds_quickcache(['model_classname', 'month', 'state_id', 'month_end_11yr', 'month_start_14yr'], timeout=60 * 60 * 2)
def get_total_records_count(model_classname, month, state_id, month_end_11yr=None,
                            month_start_14yr=None):
    classes = {
        BiharDemographicsView.__name__: BiharDemographicsView,
        BiharAPIMotherView.__name__: BiharAPIMotherView,
        BiharVaccineView.__name__: BiharVaccineView,
    }
    if month_start_14yr is None:
        return classes[model_classname].objects.filter(
            month=month,
            state_id=state_id
        ).count()
    else:
        return classes[model_classname].objects.filter(
            month=month,
            state_id=state_id,
            dob__lt=month_end_11yr,
            dob__gte=month_start_14yr,
            gender='F',
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
        'reason_closure',
        'has_bank_account',
        'age_marriage',
        'last_referral_date',
        'referral_health_problem',
        'referral_reached_date',
        'referral_reached_facility',
        'migrate_date',
        'is_alive'
    )

    # To apply pagination on database query with data size length
    limited_demographics_data = list(demographics_data_query[:CAS_API_PAGE_SIZE])
    return limited_demographics_data, get_total_records_count(BiharDemographicsView.__name__, month, state_id)


def get_mother_details(month, state_id, last_ccs_case_id):
    bihar_mother_details = BiharAPIMotherView.objects.filter(
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
        'hb',
        'lmp',
        'edd',
        'anc_1',
        'anc_2',
        'anc_3',
        'anc_4',
        'total_ifa_tablets_received',
        'ifa_consumed_7_days',
        'causes_for_ifa',
        'maternal_complications'
    )
    limited_mother_details_data = list(bihar_mother_details[:CAS_API_PAGE_SIZE])
    return limited_mother_details_data, get_total_records_count(BiharAPIMotherView.__name__, month, state_id)


def get_api_vaccine_data(month, state_id, last_person_case_id):
    vaccine_data_query = BiharVaccineView.objects.filter(
        month=month,
        state_id=state_id,
        person_id__gt=last_person_case_id
    ).order_by('person_id').values(
        'month',
        'person_id',
        'time_birth',
        'child_alive',
        'father_name',
        'mother_name',
        'father_id',
        'mother_id',
        'dob',
        'private_admit',
        'primary_admit',
        'date_last_private_admit',
        'date_return_private',
        'last_reported_fever_date',
        'due_list_date_1g_dpt_1',
        'due_list_date_2g_dpt_2',
        'due_list_date_3g_dpt_3',
        'due_list_date_5g_dpt_booster',
        'due_list_date_7gdpt_booster_2',
        'due_list_date_0g_hep_b_0',
        'due_list_date_1g_hep_b_1',
        'due_list_date_2g_hep_b_2',
        'due_list_date_3g_hep_b_3',
        'due_list_date_3g_ipv',
        'due_list_date_4g_je_1',
        'due_list_date_5g_je_2',
        'due_list_date_5g_measles_booster',
        'due_list_date_4g_measles',
        'due_list_date_0g_opv_0',
        'due_list_date_1g_opv_1',
        'due_list_date_2g_opv_2',
        'due_list_date_3g_opv_3',
        'due_list_date_5g_opv_booster',
        'due_list_date_1g_penta_1',
        'due_list_date_2g_penta_2',
        'due_list_date_3g_penta_3',
        'due_list_date_1g_rv_1',
        'due_list_date_2g_rv_2',
        'due_list_date_3g_rv_3',
        'due_list_date_4g_vit_a_1',
        'due_list_date_5g_vit_a_2',
        'due_list_date_6g_vit_a_3',
        'due_list_date_6g_vit_a_4',
        'due_list_date_6g_vit_a_5',
        'due_list_date_6g_vit_a_6',
        'due_list_date_6g_vit_a_7',
        'due_list_date_6g_vit_a_8',
        'due_list_date_7g_vit_a_9',
        'due_list_date_1g_bcg',
        'delivery_nature',
        'term_days',
        'birth_weight'
    )

    # To apply pagination on database query with data size length
    limited_vaccine_data = list(vaccine_data_query[:CAS_API_PAGE_SIZE])
    return limited_vaccine_data, get_total_records_count(BiharVaccineView.__name__, month, state_id)


def get_api_ag_school_data(month, state_id, last_person_case_id):
    month_start = force_to_date(month).replace(day=1)
    month_end = month_start + relativedelta(months=1, seconds=-1)
    month_end_11yr = month_end - relativedelta(years=11)
    month_start_14yr = month_start - relativedelta(years=14, seconds=-1)

    school_data_query = BiharDemographicsView.objects.filter(
        month=month,
        state_id=state_id,
        dob__lt=month_end_11yr,
        dob__gte=month_start_14yr,
        gender='F',
        person_id__gt=last_person_case_id
    ).order_by('person_id').values(
        'person_id',
        'person_name',
        'out_of_school_status',
        'last_class_attended_ever',
        'was_oos_ever'
    )

    # To apply pagination on database query with data size length
    limited_school_data = list(school_data_query[:CAS_API_PAGE_SIZE])
    return limited_school_data, get_total_records_count(BiharDemographicsView.__name__, month, state_id,
                                                        month_end_11yr, month_start_14yr)
