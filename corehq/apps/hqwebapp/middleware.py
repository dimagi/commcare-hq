from django.middleware.csrf import CsrfViewMiddleware, REASON_NO_CSRF_COOKIE, REASON_BAD_TOKEN

from corehq.util.soft_assert import soft_assert
from django.conf import settings


class HQCsrfViewMiddleWare(CsrfViewMiddleware):

    def _reject(self, request, reason):
        if settings.CSRF_ALWAYS_OFF and reason in [REASON_NO_CSRF_COOKIE, REASON_BAD_TOKEN]:

            warning = """Request doesn't contain a csrf token. Letting the request pass through for now. Check if we are sending csrf_token in the corresponding POST form, if not fix it. Read more here"""
            _assert = soft_assert(notify_admins=True)
            _assert(False, warning)

            return self._accept(request)
        else:
            return super(HQCsrfViewMiddleWare, self)._reject(request, reason)
