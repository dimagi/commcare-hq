import logging

from django.conf import settings

logger = logging.getLogger("smsbillables")


def log_smsbillables_error(message):
    if not settings.UNIT_TESTING:
        logger.error("[SMS Billables] %s" % message)


def log_smsbillables_info(message):
    if not settings.UNIT_TESTING:
        logger.info("[SMS Billables] %s" % message)
