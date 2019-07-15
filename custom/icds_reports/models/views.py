from __future__ import absolute_import
from __future__ import unicode_literals

from django.db import models

from custom.icds_reports.models.manager import CitusComparisonManager


class AggAwcDailyView(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    cases_household = models.IntegerField(blank=True, null=True)
    cases_person = models.IntegerField(blank=True, null=True)
    cases_person_all = models.IntegerField(blank=True, null=True)
    cases_person_has_aadhaar = models.IntegerField(blank=True, null=True)
    cases_person_beneficiary = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_14 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_15_18 = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_11_14_all = models.IntegerField(blank=True, null=True)
    cases_person_adolescent_girls_15_18_all = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating = models.IntegerField(blank=True, null=True)
    cases_child_health = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant_all = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating_all = models.IntegerField(blank=True, null=True)
    cases_child_health_all = models.IntegerField(blank=True, null=True)
    daily_attendance_open = models.IntegerField(blank=True, null=True)
    num_awcs = models.IntegerField(blank=True, null=True)
    num_launched_states = models.IntegerField(blank=True, null=True)
    num_launched_districts = models.IntegerField(blank=True, null=True)
    num_launched_blocks = models.IntegerField(blank=True, null=True)
    num_launched_supervisors = models.IntegerField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(blank=True, null=True)
    cases_person_has_aadhaar_v2 = models.IntegerField(blank=True, null=True)
    cases_person_beneficiary_v2 = models.IntegerField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'agg_awc_daily_view'


class DailyAttendanceView(models.Model):
    """Contains one row for every day that an AWC has submiteed a Daily Feeding form.

    If an AWC has submitted multiple forms for a day, the form that was submitted last
    is the one reported.
    """
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    doc_id = models.TextField(blank=True, null=True)
    pse_date = models.DateField(blank=True, null=True, help_text="Date on phone when form was completed")
    awc_open_count = models.IntegerField(
        blank=True, null=True,
        help_text="awc_opened_aww = 'yes' OR awc_opened_someone_else = 'yes'"
    )
    count = models.IntegerField(blank=True, null=True, help_text="not used")
    eligible_children = models.IntegerField(blank=True, null=True, help_text="/form/num_children")
    attended_children = models.IntegerField(blank=True, null=True, help_text="/form/num_attended_children")
    attended_children_percent = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="attended_children / eligible_children"
    )
    form_location = models.TextField(blank=True, null=True, help_text='not used')
    form_location_lat = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="Latitude of form submission"
    )
    form_location_long = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="Longitude of form submission"
    )
    image_name = models.TextField(blank=True, null=True, help_text="/form/photo_children_present")

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'daily_attendance_view'


class ChildHealthMonthlyView(models.Model):
    """Contains one row for the status of every child_health case at the end of each month
    """
    case_id = models.TextField(primary_key=True)
    awc_id = models.TextField(blank=True, null=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    person_name = models.TextField(blank=True, null=True)
    mother_name = models.TextField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    sex = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    age_in_months = models.IntegerField(
        blank=True, null=True, help_text="age in months at the end of the month"
    )
    open_in_month = models.IntegerField(
        blank=True, null=True, help_text="Open at the end of the month"
    )
    valid_in_month = models.IntegerField(
        blank=True, null=True,
        help_text="Open, alive, registered_status != 'not_registered', "
        "migration_status != 'migrated', age at start of month < 73 months"
    )
    nutrition_status_last_recorded = models.TextField(
        blank=True, null=True,
        help_text="based on zscore_grading_wfa, "
        "Either 'severely_underweight', 'moderately_underweight', or 'normal' "
        "when age at start of month < 61 months and valid_in_month "
        "or NULL otherwise"
    )
    current_month_nutrition_status = models.TextField(
        blank=True, null=True,
        help_text="nutrition_status_last_recorded if recorded in the month"
    )
    pse_days_attended = models.IntegerField(
        blank=True, null=True,
        help_text="Number of days a Daily Feeing Form has been submitted against this child case"
        "when valid_in_month and age in months between 36 and 72 months"
    )
    recorded_weight = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="weight_child if it has been recorded in the month"
    )
    recorded_height = models.DecimalField(
        max_digits=65535, decimal_places=65535, blank=True, null=True,
        help_text="height_child if it has been recorded in the month"
    )
    thr_eligible = models.IntegerField(
        blank=True, null=True,
        help_text="valid_in_month and age between 6 and 36 months"
    )
    current_month_stunting = models.TextField(
        blank=True, null=True,
        help_text="based on zscore_grading_hfa, "
        "Either 'severe', 'moderate', or 'normal' "
        "when valid_in_monthand zscore_grading_hfa changed in month"
        "or 'unmeasured' otherwise"
    )
    current_month_wasting = models.TextField(
        blank=True, null=True,
        help_text="based on zscore_grading_wfh, "
        "Either 'severe', 'moderate', or 'normal' "
        "when valid_in_monthand zscore_grading_wfh changed in month"
        "or 'unmeasured' otherwise"
    )
    fully_immunized = models.IntegerField(
        blank=True, null=True, help_text="Child has been immunized"
    )
    current_month_nutrition_status_sort = models.IntegerField(blank=True, null=True)
    current_month_stunting_sort = models.IntegerField(blank=True, null=True)
    current_month_wasting_sort = models.IntegerField(blank=True, null=True)
    current_month_stunting_v2 = models.TextField(blank=True, null=True)
    current_month_wasting_v2 = models.TextField(blank=True, null=True)
    current_month_stunting_v2_sort = models.IntegerField(blank=True, null=True)
    current_month_wasting_v2_sort = models.IntegerField(blank=True, null=True)
    aww_phone_number = models.TextField(blank=True, null=True)
    mother_phone_number = models.TextField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'child_health_monthly_view'


class AggLsMonthly(models.Model):
    """
    Contains rows for LS data.
    This view is the join between tables:
        1) agg_ls
        2) agg_awc
        3) awc_location_months
    """
    supervisor_id = models.TextField(primary_key=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(
        blank=True, null=True, help_text="1 for state rows, 2 for district rows, and so on"
    )

    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    awc_visits = models.IntegerField(help_text='Unique AWC visits by LS in the month')
    vhnd_observed = models.IntegerField(help_text='Vhnd forms submitted by LS where vhnd date in the month')
    beneficiary_vists = models.IntegerField(help_text='beneficiary visits made by LS in the month')
    num_launched_awcs = models.IntegerField(
        blank=True, null=True,
        help_text="number of AWCs that have at least one Household registration form"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'agg_ls_monthly'


class ServiceDeliveryMonthly(models.Model):
    """
    Contains rows for Service delivery report.
    """
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(
        blank=True, null=True, help_text="1 for state rows, 2 for district rows, and so on"
    )

    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(help_text='Number of AWC launched')
    num_awcs_conducted_cbe = models.IntegerField(help_text='Number of AWC conducted atleast one CBE')
    num_awcs_conducted_vhnd = models.IntegerField(help_text='Number of AWC conducted atleast one VHSND visits')
    gm_0_3 = models.IntegerField(
        blank=True, null=True,
        help_text="weighing efficiency for 0-3 years of children"
    )
    gm_3_5 = models.IntegerField(
        blank=True, null=True,
        help_text="weighing efficiency for 3-5 years of children"
    )
    children_0_3 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of children age 0-3 years"
    )
    children_3_5 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of children age 3-5 years"
    )
    children_3_6 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of children age 3-6 years"
    )

    pse_attended_21_days = models.IntegerField(
        blank=True, null=True,
        help_text="Number of children attended pse for atleast 21 days in the month"
    )
    lunch_count_21_days = models.IntegerField(
        blank=True, null=True,
        help_text="Number of children had lunch for atleast 21 days in the month"
    )
    thr_given_21_days = models.IntegerField(
        blank=True, null=True,
        help_text="Take home ration given to PW/LW and children(6-36 months) for atleast 21 days"
    )
    total_thr_candidates = models.IntegerField(
        blank=True, null=True,
        help_text="Sum of PW/LW  and children of age 6-36 months"
    )
    valid_visits = models.IntegerField(
        blank=True, null=True,
        help_text="Valid home visits"
    )
    expected_visits = models.IntegerField(
        blank=True, null=True,
        help_text="Expected Home visits"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'service_delivery_monthly'


class TakeHomeRationMonthly(models.Model):
    """
    Contains rows for THR report.
    """
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)
    thr_distribution_image_count = models.IntegerField(null=True)
    is_launched = models.TextField(null=True)
    month = models.DateField(blank=True, null=True)
    thr_given_21_days = models.IntegerField(null=True)
    total_thr_candidates = models.IntegerField(null=True)

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'thr_report_monthly'


class AggAwcMonthly(models.Model):
    """Contains one row for the status of every AWC, Supervisor, Block,
    District and State at the end of each month

    For rows for higher level of locations, the lower levels are 'All'.
    For example, in a supervisor row, awc_id = 'All'

    Common Vocabulary:
      seeking services: person_case.registered_status != 'not_registered'
      not migrated: person_case.migration_status != 'migrated'
      beneficiary: seeking services AND not migrated
    """
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(
        blank=True, null=True, help_text="1 for state rows, 2 for district rows, and so on"
    )
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)
    num_awcs = models.IntegerField(blank=True, null=True, help_text="number of AWCs")
    num_launched_states = models.IntegerField(blank=True, null=True)
    num_launched_districts = models.IntegerField(blank=True, null=True)
    num_launched_blocks = models.IntegerField(blank=True, null=True)
    num_launched_supervisors = models.IntegerField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(
        blank=True, null=True,
        help_text="number of AWCs that have at least one Household registration form"
    )
    awc_days_open = models.IntegerField(
        blank=True, null=True,
        help_text="Days an AWC has submitted an Daily Feeding Form in this month"
    )
    awc_days_pse_conducted = models.IntegerField(
        blank=True, null=True, help_text="Days an AWC has conducted pse in this month"
    )
    awc_num_open = models.IntegerField(
        blank=True, null=True, help_text="Number of AWC where awc_days_open > 1 for this month"
    )
    wer_weighed = models.IntegerField(
        blank=True, null=True, help_text="Number of children that have been weighed in the month"
    )
    wer_eligible = models.IntegerField(
        blank=True, null=True, help_text="Number of children valid_in_month and age < 60 months"
    )
    num_anc_visits = models.IntegerField(
        blank=True, null=True, help_text="Number of anc_visits in the month"
    )
    num_children_immunized = models.IntegerField(
        blank=True, null=True, help_text="Number of children immunized in the month"
    )
    cases_household = models.IntegerField(
        blank=True, null=True, help_text="Number of open household cases"
    )
    cases_person = models.IntegerField(
        blank=True, null=True,
        help_text="Number of open person cases who are beneficiaries"
    )
    cases_person_all = models.IntegerField(
        blank=True, null=True, help_text="Number of open person cases"
    )
    cases_person_has_aadhaar = models.IntegerField(blank=True, null=True, help_text="no longer used")
    cases_person_beneficiary = models.IntegerField(blank=True, null=True, help_text="no longer used")
    cases_person_adolescent_girls_11_14 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person that are female between 11 and 14 years"
    )
    cases_person_adolescent_girls_15_18 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person that are female between 15 and 18 years"
    )
    cases_person_adolescent_girls_11_14_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person_all that are female between 11 and 14 years"
    )
    cases_person_adolescent_girls_15_18_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of cases_person_all that are female between 15 and 18 years"
    )
    cases_person_referred = models.IntegerField(
        blank=True, null=True,
        help_text="Number of person cases whose last_referral_date is in this month"
    )
    cases_ccs_pregnant = models.IntegerField(
        blank=True, null=True,
        help_text="Number of ccs_record cases which are pregnant and beneficiaries"
    )
    cases_ccs_pregnant_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of ccs_record cases which are pregnant who are not migrated"
    )
    cases_ccs_lactating = models.IntegerField(
        blank=True, null=True,
        help_text="Number of ccs_record cases which have delivered in the past 183 days and are beneficiaries"
    )
    cases_ccs_lactating_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of ccs_record cases which are lactating who are not migrated"
    )
    cases_child_health = models.IntegerField(
        blank=True, null=True,
        help_text="Number of child_health cases which are beneficiaries"
    )
    cases_child_health_all = models.IntegerField(
        blank=True, null=True,
        help_text="Number of child_health cases who are not migrated"
    )
    cases_person_has_aadhaar_v2 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of child_health and ccs_records whose person case has an aadhaar number"
    )
    cases_person_beneficiary_v2 = models.IntegerField(
        blank=True, null=True,
        help_text="cases_child_health + cases_ccs_pregnant + cases_ccs_lactating"
    )
    usage_num_pse = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Daily Feeding forms submitted"
    )
    usage_num_gmp = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Growth Monitoring forms submitted"
    )
    usage_num_thr = models.IntegerField(
        blank=True, null=True,
        help_text="Number of THR forms submitted"
    )
    usage_num_home_visit = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Home Visit Scheduler forms submitted"
    )
    usage_num_bp_tri1 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Birth Preparedness forms submitted in the first trimester (from /form/new_edd)"
    )
    usage_num_bp_tri2 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Birth Preparedness forms submitted in the second trimester (from /form/new_edd)"
    )
    usage_num_bp_tri3 = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Birth Preparedness forms submitted in the third trimester (from /form/new_edd)"
    )
    usage_num_pnc = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Postnatal Care Forms submitted"
    )
    usage_num_ebf = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Exclusive Breast Feeding forms submitted"
    )
    usage_num_cf = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Complementary Feeding forms submitted"
    )
    usage_num_delivery = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Delivery forms submitted"
    )
    usage_num_due_list_ccs = models.IntegerField(
        blank=True, null=True,
        help_text="Number of due list forms submitted where tasks.type is pregnancy"
    )
    usage_num_due_list_child_health = models.IntegerField(
        blank=True, null=True,
        help_text="Number of due list forms submitted where tasks.type is child"
    )
    usage_num_hh_reg = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Register Household forms submitted"
    )
    usage_num_add_pregnancy = models.IntegerField(
        blank=True, null=True,
        help_text="Number of Add Pregnancy forms submitted"
    )
    infra_type_of_building = models.TextField(
        blank=True, null=True,
        help_text="Either 'pucca', 'semi_pucca', 'kuccha', 'partial_covered_space'"
    )
    infra_clean_water = models.IntegerField(
        blank=True, null=True,
        help_text="Latest filled out value of source_drinking_water is either [1,2,3]"
    )
    infra_functional_toilet = models.IntegerField(
        blank=True, null=True,
        help_text="Latest filled out value of toilet_functional = 'yes'"
    )
    infra_adult_weighing_scale = models.IntegerField(
        blank=True, null=True,
        help_text="available/adult_scale = 'yes' OR usable/adult_scale = 'yes'"
    )
    infra_infant_weighing_scale = models.IntegerField(
        blank=True, null=True,
        help_text="available/baby_scale = 'yes' OR usable/baby_scale = 'yes' OR available/flat_scale = 'yes'"
    )
    infra_medicine_kits = models.IntegerField(
        blank=True, null=True,
        help_text="usable/medicine_kits = 'yes'"
    )
    num_awc_infra_last_update = models.IntegerField(
        blank=True, null=True,
        help_text="last date an infrastrucutre form was submitted"
    )

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'agg_awc_monthly'


class AWWIncentiveReportMonthly(models.Model):
    """Monthly updated table that holds metrics for the incentive report"""

    # partitioned based on these fields
    state_id = models.CharField(max_length=40)
    district_id = models.TextField(blank=True, null=True)
    month = models.DateField(help_text="Will always be YYYY-MM-01")

    # primary key as it's unique for every partition
    awc_id = models.CharField(max_length=40, primary_key=True)
    is_launched = models.TextField(null=True)
    block_id = models.CharField(max_length=40)
    supervisor_id = models.TextField(null=True)
    state_name = models.TextField(null=True)
    district_name = models.TextField(null=True)
    block_name = models.TextField(null=True)
    supervisor_name = models.TextField(null=True)
    awc_name = models.TextField(null=True)
    aww_name = models.TextField(null=True)
    contact_phone_number = models.TextField(null=True)
    wer_weighed = models.SmallIntegerField(null=True)
    wer_eligible = models.SmallIntegerField(null=True)
    awc_num_open = models.SmallIntegerField(null=True)
    valid_visits = models.SmallIntegerField(null=True)
    expected_visits = models.DecimalField(null=True, max_digits=64, decimal_places=2)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'aww_incentive_report_monthly'


class AggCcsRecordMonthly(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    ccs_status = models.TextField(blank=True, null=True)
    trimester = models.TextField(blank=True, null=True)
    caste = models.TextField(blank=True, null=True)
    disabled = models.TextField(blank=True, null=True)
    minority = models.TextField(blank=True, null=True)
    resident = models.TextField(blank=True, null=True)
    valid_in_month = models.IntegerField(blank=True, null=True)
    valid_all_registered_in_month = models.IntegerField(blank=True, null=True)
    lactating = models.IntegerField(blank=True, null=True)
    pregnant = models.IntegerField(blank=True, null=True)
    lactating_all = models.IntegerField(blank=True, null=True)
    pregnant_all = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True)
    rations_21_plus_distributed = models.IntegerField(blank=True, null=True)
    tetanus_complete = models.IntegerField(blank=True, null=True)
    delivered_in_month = models.IntegerField(blank=True, null=True)
    anc1_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc2_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc3_received_at_delivery = models.IntegerField(blank=True, null=True)
    anc4_received_at_delivery = models.IntegerField(blank=True, null=True)
    registration_trimester_at_delivery = models.DecimalField(
        max_digits=65535,
        decimal_places=65535,
        blank=True,
        null=True
    )
    institutional_delivery_in_month = models.IntegerField(blank=True, null=True)
    using_ifa = models.IntegerField(blank=True, null=True)
    ifa_consumed_last_seven_days = models.IntegerField(blank=True, null=True)
    anemic_normal = models.IntegerField(blank=True, null=True)
    anemic_moderate = models.IntegerField(blank=True, null=True)
    anemic_severe = models.IntegerField(blank=True, null=True)
    anemic_unknown = models.IntegerField(blank=True, null=True)
    extra_meal = models.IntegerField(blank=True, null=True)
    resting_during_pregnancy = models.IntegerField(blank=True, null=True)
    bp1_complete = models.IntegerField(blank=True, null=True)
    bp2_complete = models.IntegerField(blank=True, null=True)
    bp3_complete = models.IntegerField(blank=True, null=True)
    pnc_complete = models.IntegerField(blank=True, null=True)
    trimester_2 = models.IntegerField(blank=True, null=True)
    trimester_3 = models.IntegerField(blank=True, null=True)
    postnatal = models.IntegerField(blank=True, null=True)
    counsel_bp_vid = models.IntegerField(blank=True, null=True)
    counsel_preparation = models.IntegerField(blank=True, null=True)
    counsel_immediate_bf = models.IntegerField(blank=True, null=True)
    counsel_fp_vid = models.IntegerField(blank=True, null=True)
    counsel_immediate_conception = models.IntegerField(blank=True, null=True)
    counsel_accessible_postpartum_fp = models.IntegerField(blank=True, null=True)
    valid_visits = models.SmallIntegerField(blank=True, null=True)
    expected_visits = models.SmallIntegerField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'agg_ccs_record_monthly'


class CcsRecordMonthlyView(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    add = models.DateField(blank=True, null=True)
    age_in_months = models.IntegerField(blank=True, null=True)
    anc_hemoglobin = models.DecimalField(max_digits=64, decimal_places=20, blank=True, null=True)
    anc_weight = models.SmallIntegerField(blank=True, null=True)
    anemic_moderate = models.IntegerField(blank=True, null=True)
    anemic_normal = models.IntegerField(blank=True, null=True)
    anemic_severe = models.IntegerField(blank=True, null=True)
    anemic_unknown = models.IntegerField(blank=True, null=True)
    bleeding = models.SmallIntegerField(blank=True, null=True)
    blurred_vision = models.SmallIntegerField(blank=True, null=True)
    bp_dia = models.SmallIntegerField(blank=True, null=True)
    bp_sys = models.SmallIntegerField(blank=True, null=True)
    breastfed_at_birth = models.SmallIntegerField(blank=True, null=True)
    case_id = models.TextField(primary_key=True)
    convulsions = models.SmallIntegerField(blank=True, null=True)
    counsel_accessible_postpartum_fp = models.IntegerField(blank=True, null=True)
    counsel_bp_vid = models.IntegerField(blank=True, null=True)
    counsel_fp_methods = models.IntegerField(blank=True, null=True)
    counsel_fp_vid = models.IntegerField(blank=True, null=True)
    counsel_immediate_bf = models.IntegerField(blank=True, null=True)
    counsel_immediate_conception = models.IntegerField(blank=True, null=True)
    counsel_preparation = models.IntegerField(blank=True, null=True)
    delivery_nature = models.SmallIntegerField(blank=True, null=True)
    edd = models.DateField(blank=True, null=True)
    home_visit_date = models.DateField(blank=True, null=True)
    ifa_consumed_last_seven_days = models.IntegerField(blank=True, null=True)
    institutional_delivery_in_month = models.IntegerField(blank=True, null=True)
    institutional_delivery = models.IntegerField(blank=True, null=True)
    is_ebf = models.SmallIntegerField(blank=True, null=True)
    last_date_thr = models.DateField(blank=True, null=True)
    mobile_number = models.TextField(blank=True, null=True)
    num_anc_complete = models.SmallIntegerField(blank=True, null=True)
    num_pnc_visits = models.SmallIntegerField(blank=True, null=True)
    num_rations_distributed = models.IntegerField(blank=True, null=True)
    opened_on = models.DateField(blank=True, null=True)
    person_name = models.TextField(blank=True, null=True)
    preg_order = models.SmallIntegerField(blank=True, null=True)
    pregnant = models.IntegerField(blank=True, null=True)
    pregnant_all = models.IntegerField(blank=True, null=True)
    rupture = models.SmallIntegerField(blank=True, null=True)
    swelling = models.SmallIntegerField(blank=True, null=True)
    trimester = models.IntegerField(blank=True, null=True)
    tt_1 = models.DateField(blank=True, null=True)
    tt_2 = models.DateField(blank=True, null=True)
    using_ifa = models.IntegerField(blank=True, null=True)
    lactating = models.IntegerField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    open_in_month = models.SmallIntegerField(blank=True, null=True)
    closed = models.SmallIntegerField(blank=True, null=True)
    anc_abnormalities = models.SmallIntegerField(blank=True, null=True)
    date_death = models.DateField(blank=True, null=True)
    eating_extra = models.SmallIntegerField(blank=True, null=True)
    resting = models.SmallIntegerField(blank=True, null=True)
    immediate_breastfeeding = models.SmallIntegerField(blank=True, null=True)
    caste = models.TextField(blank=True, null=True)
    disabled = models.TextField(blank=True, null=True)
    minority = models.TextField(blank=True, null=True)
    resident = models.TextField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'ccs_record_monthly_view'


class AggChildHealthMonthly(models.Model):
    """Contains one row every month for AWC, Superviosr, Block, District, State, gender and age_tranche.
    Each indicator is summed up to the above groupings.

    Common Vocabulary:
      seeking services: person_case.registered_status != 'not_registered'
      not migrated: person_case.migration_status != 'migrated'
      beneficiary: seeking services AND not migrated
    """
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    month_display = models.TextField(blank=True, null=True)
    gender = models.TextField(blank=True, null=True, help_text="person.sex")
    age_tranche = models.TextField(
        blank=True, null=True,
        help_text="Either 0 (<= 28 days), 6 (<= 6 months), 12 (<= 12 months), 24, 36, 48, 60, 72"
    )
    caste = models.TextField(blank=True, null=True, help_text="household.hh_caste")
    minority = models.TextField(blank=True, null=True, help_text="household.hh_minority")
    resident = models.TextField(blank=True, null=True, help_text="person.resident")
    valid_in_month = models.IntegerField(
        blank=True, null=True, help_text="case open, alive, beneficiary"
    )
    valid_all_registered_in_month = models.IntegerField(
        blank=True, null=True, help_text="case open, alive, not migrated"
    )
    wer_eligible = models.IntegerField(
        blank=True, null=True, help_text="age <= 60 months and valid_in_month"
    )
    nutrition_status_weighed = models.IntegerField(
        blank=True, null=True,
        help_text="wer_eligible AND zscore_grading_wfa recorded in this month"
    )
    nutrition_status_unweighed = models.IntegerField(
        blank=True, null=True,
        help_text="wer_eligible AND zscore_grading_wfa not recorded in this month"
    )
    nutrition_status_normal = models.IntegerField(
        blank=True, null=True, help_text="wer_eligible AND zscore_grading_wfa = 'green' or 'white'"
    )
    nutrition_status_moderately_underweight = models.IntegerField(
        blank=True, null=True, help_text="wer_eligible AND zscore_grading_wfa = 'yellow'"
    )
    nutrition_status_severely_underweight = models.IntegerField(
        blank=True, null=True, help_text="wer_eligible AND zscore_grading_wfa = 'red'"
    )
    height_eligible = models.IntegerField(
        blank=True, null=True, help_text="age > 6 months < 60 months and valid_in_month"
    )
    height_measured_in_month = models.IntegerField(
        blank=True, null=True, help_text="height_eligible and height_child recorded in this month"
    )
    wasting_moderate = models.IntegerField(blank=True, null=True, help_text="to be removed")
    wasting_severe = models.IntegerField(blank=True, null=True, help_text="to be removed")
    wasting_normal = models.IntegerField(blank=True, null=True, help_text="to be removed")
    wasting_moderate_v2 = models.IntegerField(
        blank=True, null=True,
        help_text="zscore_grading_wfh recorded in month AND = 'yellow' OR muac_grading recorded in month and = yellow"
    )
    wasting_severe_v2 = models.IntegerField(
        blank=True, null=True,
        help_text="zscore_grading_wfh recorded in month AND = 'red' OR muac_grading recorded in month and = red"
    )
    wasting_normal_v2 = models.IntegerField(
        blank=True, null=True,
        help_text="zscore_grading_wfh recorded in month AND = 'green' OR muac_grading recorded in month and = green"
    )
    stunting_moderate = models.IntegerField(blank=True, null=True, help_text="to be removed")
    stunting_severe = models.IntegerField(blank=True, null=True, help_text="to be removed")
    stunting_normal = models.IntegerField(blank=True, null=True, help_text="to be removed")
    zscore_grading_hfa_moderate = models.IntegerField(blank=True, null=True)
    zscore_grading_hfa_severe = models.IntegerField(blank=True, null=True)
    zscore_grading_hfa_normal = models.IntegerField(blank=True, null=True)
    thr_eligible = models.IntegerField(blank=True, null=True, help_text="valid_in_month and > 6 AND <= 36 months")
    days_ration_given_child = models.IntegerField(
        blank=True, null=True, help_text="thr_eligible AND rations given in month"
    )
    rations_21_plus_distributed = models.IntegerField(
        blank=True, null=True, help_text="days_ration_given_child > 21"
    )
    born_in_month = models.IntegerField(blank=True, null=True, help_text="beneficiary with dob in this month")
    low_birth_weight_in_month = models.IntegerField(
        blank=True, null=True, help_text="born_in_month AND low_birth_weight = 'yes'"
    )
    bf_at_birth = models.IntegerField(
        blank=True, null=True, help_text="born_in_month AND breastfed_within_first = 'yes'"
    )
    ebf_eligible = models.IntegerField(blank=True, null=True, help_text="valid_in_month AND <= 6 months")
    ebf_in_month = models.IntegerField(
        blank=True, null=True, help_text="ebf_eligible AND last EBF form is_ebf = 'yes'",
    )
    counsel_adequate_bf = models.IntegerField(
        blank=True, null=True, help_text="ebf_eligible AND counsel_adequate_bf = 'yes' in any form ever"
    )
    counsel_ebf = models.IntegerField(
        blank=True, null=True,
        help_text="ebf_eligible AND (counsel_exclusive_bf = 'yes' OR counsel_only_milk = 'yes' in an form ever)"
    )
    cf_eligible = models.IntegerField(
        blank=True, null=True, help_text="valid_in_month AND > 6 months <= 24 months"
    )
    cf_in_month = models.IntegerField(
        blank=True, null=True,
        help_text="cf_eligible AND complementary feeding form submitted this month"
    )
    cf_diet_diversity = models.IntegerField(
        blank=True, null=True, help_text="cf_eligible AND last form diet_diversity = 'yes'"
    )
    cf_diet_quantity = models.IntegerField(
        blank=True, null=True, help_text="cf_eligible AND last form diet_quantity = 'yes'"
    )
    cf_demo = models.IntegerField(
        blank=True, null=True,
        help_text="cf_eligible AND demo_comp_feeding = 'yes' any form submitted"
    )
    cf_handwashing = models.IntegerField(
        blank=True, null=True, help_text="cf_eligible AND hand_wash = 1 in last form"
    )
    counsel_pediatric_ifa = models.IntegerField(
        blank=True, null=True,
        help_text="cf_eligible AND counselled_pediatric_ifa = 'yes' in any form submitted"
    )
    cf_initiation_eligible = models.IntegerField(
        blank=True, null=True, help_text="valid_in_month AND > 6 months <= 8 months"
    )
    cf_initiation_in_month = models.IntegerField(
        blank=True, null=True, help_text="cf_initiation_eligible AND comp_feeding = 'yes' in any form submitted"
    )
    pnc_eligible = models.IntegerField(blank=True, null=True, help_text="valid_in_month and < 20 days")
    counsel_increase_food_bf = models.IntegerField(
        blank=True, null=True,
        help_text="pnc_eligible AND counsel_increase_food_bf = 'yes' in any form submitted"
    )
    counsel_manage_breast_problems = models.IntegerField(
        blank=True, null=True, help_text="pnc_eligible AND counsel_breast = 'yes' in any form submitted"
    )
    fully_immunized_eligible = models.IntegerField(
        blank=True, null=True, help_text="valid_in_month AND > 12 months"
    )
    fully_immunized_on_time = models.IntegerField(
        blank=True, null=True,
        help_text="fully_immunized_eligible AND task_case.immun_one_year_date before one year old"
    )
    fully_immunized_late = models.IntegerField(
        blank=True, null=True,
        help_text="fully_immunized_eligible AND task_case.immun_one_year_date after one year old"
    )
    weighed_and_height_measured_in_month = models.IntegerField(
        blank=True, null=True, help_text="nutrition_status_weighed AND height_measured_in_month"
    )
    weighed_and_born_in_month = models.IntegerField(
        blank=True, null=True, help_text="nutrition_status_weighed AND low_birth_weight_in_month"
    )
    zscore_grading_hfa_recorded_in_month = models.IntegerField(blank=True, null=True)
    zscore_grading_wfh_recorded_in_month = models.IntegerField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'agg_child_health_monthly'


class AwcLocationMonths(models.Model):
    awc_id = models.TextField(primary_key=True)
    awc_name = models.TextField(blank=True, null=True)
    awc_site_code = models.TextField(blank=True, null=True)
    supervisor_id = models.TextField(blank=True, null=True)
    supervisor_name = models.TextField(blank=True, null=True)
    supervisor_site_code = models.TextField(blank=True, null=True)
    block_id = models.TextField(blank=True, null=True)
    block_name = models.TextField(blank=True, null=True)
    block_site_code = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    district_site_code = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    state_site_code = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    block_map_location_name = models.TextField(blank=True, null=True)
    district_map_location_name = models.TextField(blank=True, null=True)
    state_map_location_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    month_display = models.TextField(blank=True, null=True)
    aww_name = models.TextField(blank=True, null=True)
    contact_phone_number = models.TextField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'awc_location_months'


class DishaIndicatorView(models.Model):
    block_id = models.TextField(primary_key=True)
    block_name = models.TextField(blank=True, null=True)
    district_id = models.TextField(blank=True, null=True)
    district_name = models.TextField(blank=True, null=True)
    state_id = models.TextField(blank=True, null=True)
    state_name = models.TextField(blank=True, null=True)
    aggregation_level = models.IntegerField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)
    # agg_awc Indicator
    cases_household = models.IntegerField(blank=True, null=True)
    # agg_awc_monthly indicators
    cases_person_all = models.IntegerField(blank=True, null=True)
    cases_person = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating = models.IntegerField(blank=True, null=True)
    cases_child_health_all = models.IntegerField(blank=True, null=True)
    cases_child_health = models.IntegerField(blank=True, null=True)
    medicine_kit_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    infant_weighing_scale_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    adult_weighing_scale_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    clean_water_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    functional_toilet_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    # agg_ccs_record_monthly indicators
    resting_during_pregnancy_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    extra_meal_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    counsel_immediate_bf_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    # agg_child_health_monthly indicators
    nutrition_status_weighed_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    height_measured_in_month_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    nutrition_status_unweighed = models.IntegerField(blank=True, null=True)
    nutrition_status_severely_underweight_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    nutrition_status_moderately_underweight_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    wasting_severe_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    wasting_moderate_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    stunting_severe_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)
    stunting_moderate_percent = models.DecimalField(
        max_digits=16, decimal_places=8, blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'icds_disha_indicators'


class NICIndicatorsView(models.Model):
    state_id = models.TextField(primary_key=True)
    state_name = models.TextField(blank=True, null=True)
    month = models.DateField(blank=True, null=True)

    cases_household = models.IntegerField(blank=True, null=True)
    cases_ccs_pregnant = models.IntegerField(blank=True, null=True)
    cases_ccs_lactating = models.IntegerField(blank=True, null=True)
    cases_child_health = models.IntegerField(blank=True, null=True)
    num_launched_awcs = models.IntegerField(blank=True, null=True)
    ebf_in_month = models.IntegerField(blank=True, null=True)
    cf_initiation_in_month = models.IntegerField(blank=True, null=True)
    bf_at_birth = models.IntegerField(blank=True, null=True)

    objects = CitusComparisonManager()

    class Meta(object):
        app_label = 'icds_reports'
        managed = False
        db_table = 'nic_indicators'
