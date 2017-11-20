from __future__ import absolute_import
from django.conf import settings

ISSUE_TRACKER_APP_ID = '48cc1709b7f62ffea24cc6634a005734'


TABLEAU_TICKET_URL = settings.TABLEAU_URL_ROOT + "trusted/"
TABLEAU_VIEW_URL = settings.TABLEAU_URL_ROOT + "#/views/"
TABLEAU_USERNAME = "reportviewer"
TABLEAU_INVALID_TOKEN = '-1'

BHD_ROLE = 'BHD (For VL Dashboard Testing)'


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
