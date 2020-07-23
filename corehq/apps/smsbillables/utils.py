import logging

from django.conf import settings
from django.utils.encoding import force_text

from django_countries.data import COUNTRIES
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE

logger = logging.getLogger("smsbillables")


def country_name_from_isd_code_or_empty(isd_code):
    cc = COUNTRY_CODE_TO_REGION_CODE.get(isd_code)
    return force_text(COUNTRIES.get(cc[0])) if cc else ''


def log_smsbillables_error(message):
    if not settings.UNIT_TESTING:
        logger.error("[SMS Billables] %s" % message)


def log_smsbillables_info(message):
    if not settings.UNIT_TESTING:
        logger.info("[SMS Billables] %s" % message)
