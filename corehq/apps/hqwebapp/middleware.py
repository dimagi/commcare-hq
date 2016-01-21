import logging

from django.middleware.csrf import CsrfViewMiddleware, REASON_NO_CSRF_COOKIE, REASON_BAD_TOKEN
from django.conf import settings

from corehq.util.soft_assert import soft_assert


logger = logging.getLogger('')


class HQCsrfViewMiddleWare(CsrfViewMiddleware):

    def _reject(self, request, reason):
        request_url = request.path
        referring_url = request.META.get('HTTP_REFERER', 'Unknown URL')
        warning = "Request at {url} doesn't contain a csrf token. "\
                  "Referring url is {referer}. Letting the request pass through for now. "\
                  "Check if we are sending csrf_token in the corresponding POST form, if not fix it. "\
                  "Read more here https://github.com/dimagi/commcare-hq/pull/9227".format(
                      url=request_url,
                      referer=referring_url,
                  )
        logger.error(warning)  # send it couchlog for log-analysis
        _assert = soft_assert('{}@{}'.format('sreddy+logs', 'dimagi.com'), exponential_backoff=False)
        _assert(False, warning)

        if request_url.find('login'):
            # exempt login URLs from csrf, but still get failure logs
            self._accept(request)

        if settings.CSRF_SOFT_MODE and reason in [REASON_NO_CSRF_COOKIE, REASON_BAD_TOKEN]:
            return self._accept(request)
        else:
            return super(HQCsrfViewMiddleWare, self)._reject(request, reason)
