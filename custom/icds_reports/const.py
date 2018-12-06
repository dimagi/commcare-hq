from __future__ import absolute_import
from __future__ import unicode_literals

import pytz
from django.conf import settings

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

class LocationTypes(object):
    STATE = 'state'
    DISTRICT = 'district'
    BLOCK = 'block'
    SUPERVISOR = 'supervisor'
    AWC = 'awc'


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


ICDS_SUPPORT_EMAIL = 'icds-support@dimagi.com'


CHILDREN_EXPORT = 1
PREGNANT_WOMEN_EXPORT = 2
DEMOGRAPHICS_EXPORT = 3
SYSTEM_USAGE_EXPORT = 4
AWC_INFRASTRUCTURE_EXPORT = 5
BENEFICIARY_LIST_EXPORT = 6
ISSNIP_MONTHLY_REGISTER_PDF = 7
AWW_INCENTIVE_REPORT = 8

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


AWC_LOCATION_TABLE_ID = 'static-awc_location'
USAGE_TABLE_ID = 'static-usage_forms'
PERSON_TABLE_ID = 'static-person_cases_v2'
HOUSEHOLD_TABLE_ID = 'static-household_cases'
AWW_USER_TABLE_ID = 'static-commcare_user_cases'
DAILY_FEEDING_TABLE_ID = 'static-daily_feeding_forms'

DASHBOARD_DOMAIN = 'icds-dashboard-qa' if settings.SERVER_ENVIRONMENT == 'softlayer' else 'icds-cas'
