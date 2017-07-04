import logging

from django.middleware.csrf import CsrfViewMiddleware

from corehq.util.soft_assert import soft_assert

logger = logging.getLogger('')


class HQCsrfViewMiddleWare(CsrfViewMiddleware):

    def _reject(self, request, reason):
        request_url = request.path
        referring_url = request.META.get('HTTP_REFERER', 'Unknown URL')
        warning = "{ajax}Request at {url} doesn't contain a csrf token. Referring url is {referer}."\
                  "Possibly related to https://github.com/dimagi/commcare-hq/pull/16008".format(
                      url=request_url,
                      referer=referring_url,
                      ajax=('Ajax ' if request.is_ajax() else '')
                  )
        _assert = soft_assert('{}@{}'.format('mkangia+logs', 'dimagi.com'), exponential_backoff=False)
        _assert(False, warning)

        return super(HQCsrfViewMiddleWare, self)._reject(request, reason)
