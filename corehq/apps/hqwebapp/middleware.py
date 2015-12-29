import logging

from django.middleware.csrf import CsrfViewMiddleware, REASON_NO_CSRF_COOKIE, REASON_BAD_TOKEN
from django.conf import settings


logger = logging.getLogger('')


class HQCsrfViewMiddleWare(CsrfViewMiddleware):

    def _reject(self, request, reason):
        if settings.CSRF_ALWAYS_OFF and reason in [REASON_NO_CSRF_COOKIE, REASON_BAD_TOKEN]:

            warning = "Request at {url} doesn't contain a csrf token. Letting the request pass through for now. "\
                      "Check if we are sending csrf_token in the corresponding POST form, if not fix it. "\
                      "Read more here https://github.com/dimagi/commcare-hq/pull/9227".format(
                          url=request.path
                      )
            logger.error(warning)
            return self._accept(request)
        else:
            warning = "The request at {url} doesn't contain a csrf token. This has been rejected".format(
                          url=request.path
                      )
            logger.error(warning)
            return super(HQCsrfViewMiddleWare, self)._reject(request, reason)
