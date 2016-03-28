import logging

from django.utils.encoding import force_unicode

from django_countries.data import COUNTRIES

from phonenumbers import COUNTRY_CODE_TO_REGION_CODE

logger = logging.getLogger("smsbillables")


def country_name_from_isd_code_or_empty(isd_code):
    cc = COUNTRY_CODE_TO_REGION_CODE.get(isd_code)
    return force_unicode(COUNTRIES.get(cc[0])) if cc else ''


def log_smsbillables_error(message):
    logger.error("[SMS Billables] %s" % message)


def log_smsbillables_info(message):
    logger.info("[SMS Billables] %s" % message)
