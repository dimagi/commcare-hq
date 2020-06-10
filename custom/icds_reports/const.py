from datetime import date

from django.conf import settings

import pytz

from custom.icds_reports.data_pull.data_pulls import (
    AndhraPradeshMonthly,
    MonthlyPerformance,
    VHSNDMonthlyReport,
)

ISSUE_TRACKER_APP_ID = '48cc1709b7f62ffea24cc6634a005734'


INDIA_TIMEZONE = pytz.timezone('Asia/Kolkata')

TABLEAU_TICKET_URL = settings.TABLEAU_URL_ROOT + "trusted/"
TABLEAU_VIEW_URL = settings.TABLEAU_URL_ROOT + "#/views/"
TABLEAU_USERNAME = "reportviewer"
TABLEAU_INVALID_TOKEN = '-1'

BHD_ROLE = 'BHD (For VL Dashboard Testing)'

UCR_PILLOWS = ['kafka-ucr-static', 'kafka-ucr-static-cases',
               'kafka-ucr-static-forms', 'kafka-ucr-static-awc-location',
               'kafka-ucr-main']


class NavigationSections:
    MATERNAL_CHILD = 'maternal_child'
    ICDS_CAS_REACH = 'icds_cas_reach'
    DEMOGRAPHICS = 'demographics'
    AWC_INFRASTRUCTURE = 'awc_infrastructure'


class SDDSections:
    PW_LW_CHILDREN = 'pw_lw_children'
    CHILDREN = 'children'


class LocationTypes(object):
    STATE = 'state'
    DISTRICT = 'district'
    BLOCK = 'block'
    SUPERVISOR = 'supervisor'
    AWC = 'awc'


class AggregationLevels(object):
    STATE = 1
    DISTRICT = 2
    BLOCK = 3
    SUPERVISOR = 4
    AWC = 5


class ChartColors(object):
    PINK = '#fcb18d'
    ORANGE = '#fa683c'
    RED = '#bf231d'
    BLUE = '#005ebd'


class MapColors(object):
    RED = '#de2d26'
    ORANGE = '#fc9272'
    BLUE = '#006fdf'
    PINK = '#fee0d2'
    GREY = '#9D9D9D'


LOCATION_TYPES = [
    LocationTypes.STATE,
    LocationTypes.DISTRICT,
    LocationTypes.BLOCK,
    LocationTypes.SUPERVISOR,
    LocationTypes.AWC
]


HELPDESK_ROLES = [
    'BHD',
    'DHD',
    'CPMU',
    'SHD',
    'Test BHD (For VL Dashboard QA)',
    'Test DHD (For VL Dashboard QA)',
    'Test SHD (For VL Dashboard QA)',
    'Test CPMU (For VL Dashboard QA)'
]


CHILDREN_EXPORT = 1
PREGNANT_WOMEN_EXPORT = 2
DEMOGRAPHICS_EXPORT = 3
SYSTEM_USAGE_EXPORT = 4
AWC_INFRASTRUCTURE_EXPORT = 5
GROWTH_MONITORING_LIST_EXPORT = 6
ISSNIP_MONTHLY_REGISTER_PDF = 7
AWW_INCENTIVE_REPORT = 8
LS_REPORT_EXPORT = 9
THR_REPORT_EXPORT = 10
DASHBOARD_USAGE_EXPORT = 11
SERVICE_DELIVERY_REPORT = 12
CHILD_GROWTH_TRACKER_REPORT = 13
AWW_ACTIVITY_REPORT = 14

AGG_COMP_FEEDING_TABLE = 'icds_dashboard_comp_feed_form'
AGG_CCS_RECORD_CF_TABLE = 'icds_dashboard_ccs_record_cf_forms'
AGG_CCS_RECORD_PNC_TABLE = 'icds_dashboard_ccs_record_postnatal_forms'
AGG_CHILD_HEALTH_PNC_TABLE = 'icds_dashboard_child_health_postnatal_forms'
AGG_CHILD_HEALTH_THR_TABLE = 'icds_dashboard_child_health_thr_forms'
AGG_CCS_RECORD_THR_TABLE = 'icds_dashboard_ccs_record_thr_forms'
AGG_CCS_RECORD_BP_TABLE = 'icds_dashboard_ccs_record_bp_forms'
AGG_CCS_RECORD_DELIVERY_TABLE = 'icds_dashboard_ccs_record_delivery_forms'
AGG_DAILY_FEEDING_TABLE = 'icds_dashboard_daily_feeding_forms'
AGG_GROWTH_MONITORING_TABLE = 'icds_dashboard_growth_monitoring_forms'
AGG_INFRASTRUCTURE_TABLE = 'icds_dashboard_infrastructure_forms'
AWW_INCENTIVE_TABLE = 'icds_dashboard_aww_incentive'
AGG_LS_AWC_VISIT_TABLE = 'icds_dashboard_ls_awc_visits_forms'
AGG_LS_VHND_TABLE = 'icds_dashboard_ls_vhnd_forms'
AGG_LS_BENEFICIARY_TABLE = 'icds_dashboard_ls_beneficiary_forms'
AGG_THR_V2_TABLE = 'icds_dashboard_thr_v2'
AGG_DASHBOARD_ACTIVITY = 'icds_dashboard_user_activity'
AGG_ADOLESCENT_GIRLS_REGISTRATION_TABLE = 'icds_dashboard_adolescent_girls_registration'
AGG_GOV_DASHBOARD_TABLE = 'agg_gov_dashboard'
AGG_MIGRATION_TABLE = 'icds_dashboard_migration_forms'
AGG_AVAILING_SERVICES_TABLE = 'icds_dashboard_availing_service_forms'

AWC_LOCATION_TABLE_ID = 'static-awc_location'
USAGE_TABLE_ID = 'static-usage_forms'
HOUSEHOLD_TABLE_ID = 'static-household_cases'
AWW_USER_TABLE_ID = 'static-commcare_user_cases'
DAILY_FEEDING_TABLE_ID = 'static-daily_feeding_forms'
AGG_SDR_TABLE = 'agg_service_delivery_report'
BIHAR_API_DEMOGRAPHICS_TABLE = 'bihar_api_demographics'
BIHAR_API_MOTHER_DETAILS_TABLE = 'bihar_api_mother_details'
CHILD_VACCINE_TABLE = 'child_vaccines'
CHILD_DELIVERY_FORM_ID = 'static-child_delivery_forms'

DASHBOARD_DOMAIN = 'icds-dashboard-qa' if settings.SERVER_ENVIRONMENT in ('india', 'icds-staging') else 'icds-cas'

THREE_MONTHS = 60 * 60 * 24 * 95

VALID_LEVELS_FOR_DUMP = [
    '1',  # state
    '2',  # district
    '3',  # block
]

DISTRIBUTED_TABLES = [
    (AGG_CCS_RECORD_DELIVERY_TABLE, 'supervisor_id'),
    (AGG_COMP_FEEDING_TABLE, 'supervisor_id'),
    (AGG_CCS_RECORD_CF_TABLE, 'supervisor_id'),
    (AGG_CHILD_HEALTH_THR_TABLE, 'supervisor_id'),
    (AGG_GROWTH_MONITORING_TABLE, 'supervisor_id'),
    (AGG_CHILD_HEALTH_PNC_TABLE, 'supervisor_id'),
    (AGG_CCS_RECORD_PNC_TABLE, 'supervisor_id'),
    (AGG_CCS_RECORD_BP_TABLE, 'supervisor_id'),
    (AGG_CCS_RECORD_THR_TABLE, 'supervisor_id'),
    (AGG_DAILY_FEEDING_TABLE, 'supervisor_id'),
    ('child_health_monthly', 'supervisor_id'),
    ('ccs_record_monthly', 'supervisor_id'),
    ('daily_attendance', 'supervisor_id'),
]

REFERENCE_TABLES = [
    'awc_location',
    'icds_months'
]

AADHAR_SEEDED_BENEFICIARIES = 'Aadhaar-seeded Beneficiaries'
CHILDREN_ENROLLED_FOR_ANGANWADI_SERVICES = 'Children enrolled for Anganwadi Services'
PREGNANT_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES = 'Pregnant women enrolled for Anganwadi Services'
LACTATING_WOMEN_ENROLLED_FOR_ANGANWADI_SERVICES = 'Lactating women enrolled for Anganwadi Services'
ADOLESCENT_GIRLS_ENROLLED_FOR_ANGANWADI_SERVICES = 'Adolescent girls enrolled for Anganwadi Services'

OUT_OF_SCHOOL_ADOLESCENT_GIRLS_11_14_YEARS = 'Out of school Adolescent girls (11-14 years)'
NUM_OF_ADOLESCENT_GIRLS_11_14_YEARS = 'Number of adolescent girls (11-14 years)'
NUM_OUT_OF_SCHOOL_ADOLESCENT_GIRLS_11_14_YEARS = 'Number of out of school adolescent girls (11-14 years)'


CAS_API_PAGE_SIZE = 10000

CUSTOM_DATA_PULLS = {
    AndhraPradeshMonthly.slug: AndhraPradeshMonthly,
    MonthlyPerformance.slug: MonthlyPerformance,
    VHSNDMonthlyReport.slug: VHSNDMonthlyReport,
}

THR_REPORT_CONSOLIDATED = 'consolidated'
THR_REPORT_BENEFICIARY_TYPE = 'beneficiary_wise'
THR_REPORT_DAY_BENEFICIARY_TYPE = 'days_beneficiary_wise'
THR_21_DAYS_THRESHOLD_DATE = date(2020, 3, 1)
