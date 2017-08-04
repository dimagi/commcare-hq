import base64
import hashlib
import hmac
from functools import wraps

from django.http import HttpResponse

import settings
from corehq.util.soft_assert.api import soft_assert

_soft_assert = soft_assert(notify_admins=True)


def validate_request_hmac(setting_name):
    """
    Decorator to validate request sender using a shared secret
    to compare the HMAC of the request body with
    the value of the `X-MAC-DIGEST' header.

    Example request:

        digest = base64.b64encode(hmac.new(shared_secret, data, hashlib.sha256).digest())
        requests.post(url, data=data, headers={'X-MAC-DIGEST': digest})

    :param setting_name: The name of the Django setting that holds the secret key
    """
    shared_key = getattr(settings, setting_name, None)

    def _outer(fn):
        @wraps(fn)
        def _inner(request, *args, **kwargs):
            _soft_assert(shared_key, 'Missing shared auth setting: {}'.format(setting_name))
            expected_digest = request.META.get('HTTP_X_MAC_DIGEST', None)
            if not expected_digest or not shared_key:
                return HttpResponse(status=401)

            hm = hmac.new(shared_key, request.body, hashlib.sha256)
            digest = base64.b64encode(hm.digest())

            if expected_digest != digest:
                return HttpResponse(status=401)

            return fn(request, *args, **kwargs)
        return _inner
    return _outer
