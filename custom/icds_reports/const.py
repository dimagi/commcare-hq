from django.conf import settings

APP_ID = '361a135293a84427afc947beee1acdfe'


TABLEAU_TICKET_URL = settings.TABLEAU_URL_ROOT + "trusted/"
TABLEAU_VIEW_URL = settings.TABLEAU_URL_ROOT + "#/views/"
TABLEAU_USERNAME = "reportviewer"
TABLEAU_INVALID_TOKEN = '-1'

BHD_ROLE = 'BHD (For VL Dashboard Testing)'


class LocationTypes(object):
    STATE = 'state'
    BLOCK = 'block'
    SUPERVISOR = 'supervisor'
    AWC = 'awc'
