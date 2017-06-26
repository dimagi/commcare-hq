from django.conf import settings


TABLEAU_TICKET_URL = settings.TABLEAU_URL_ROOT + "trusted/"
TABLEAU_VIEW_URL = settings.TABLEAU_URL_ROOT + "#/views/"
TABLEAU_USERNAME = "reportviewer"
TABLEAU_INVALID_TOKEN = '-1'


class LocationTypes(object):
    BLOCK = 'block'
    SUPERVISOR = 'supervisor'
    AWC = 'awc'
