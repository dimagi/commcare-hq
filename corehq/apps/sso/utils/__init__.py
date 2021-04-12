import logging

logger = logging.getLogger('sso')


def log_sso_error(message, show_stack_trace=False):
    logger.error("[SSO] %s" % message, exc_info=show_stack_trace)


def log_sso_info(message):
    logger.info("[SSO] %s" % message)
