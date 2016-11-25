from django.conf import settings


TABLEU_TICKET_URL = settings.TABLEAU_URL_ROOT + "trusted/"
TABLEAU_VIEW_URL = settings.TABLEAU_URL_ROOT + "#/views/"
TABLEAU_USERNAME = "reportviewer"
TABLEAU_INVALID_TOKEN = '-1'
WORKBOOK_NAME = "DashboardR5"
DEFAULT_WORKSHEET = "Dashboard"
