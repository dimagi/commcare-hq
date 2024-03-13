import base64
import hashlib
import hmac
import logging
from functools import wraps

from django.conf import settings
from django.http import HttpResponse

from corehq.util.soft_assert.api import soft_assert

auth_logger = logging.getLogger("commcare_auth")
_soft_assert = soft_assert(notify_admins=True)


def convert_to_bytestring_if_unicode(shared_key):
    return shared_key.encode('utf-8') if isinstance(shared_key, str) else shared_key


def get_hmac_digest(shared_key, data):
    shared_key_bytes = convert_to_bytestring_if_unicode(shared_key)
    data_bytes = convert_to_bytestring_if_unicode(data)
    hm = hmac.new(shared_key_bytes, data_bytes, hashlib.sha256)
    digest = base64.b64encode(hm.digest())
    return digest.decode('utf-8')


def validate_request_hmac(setting_name, audit_user='system'):
    """
    Decorator to validate request sender using a shared secret
    to compare the HMAC of the request body or query string with
    the value of the `X-MAC-DIGEST' header.

    Example requests:

        POST:

        digest = base64.b64encode(hmac.new(shared_secret, data, hashlib.sha256).digest())
        requests.post(url, data=data, headers={'X-MAC-DIGEST': digest})

        GET:

        params = urlencode(query_params)
        digest = base64.b64encode(hmac.new(shared_secret, params, hashlib.sha256).digest())
        requests.get(url, params=params, headers={'X-MAC-DIGEST': digest})


    :param setting_name: The name of the Django setting that holds the secret key
    :param audit_user: The username to report to an auditing system, since these requests are anonymous but auth'd.
    """
    def _outer(fn):
        shared_key = getattr(settings, setting_name, None)

        @wraps(fn)
        def _inner(request, *args, **kwargs):
            data = request.get_full_path() if request.method == 'GET' else request.body

            _soft_assert(shared_key, 'Missing shared auth setting: {}'.format(setting_name))
            expected_digest = request.META.get('HTTP_X_MAC_DIGEST', None)
            if not expected_digest or not shared_key:
                auth_logger.info(
                    "Request rejected reason=%s request=%s",
                    "hmac:missing_key" if not shared_key else "hmac:missing_header", request.path
                )
                return HttpResponse(status=401)

            digest = get_hmac_digest(shared_key, data)

            if expected_digest != digest:
                auth_logger.info(
                    "Request rejected reason=%s request=%s",
                    "hmac:digest_mismatch", request.path
                )
                return HttpResponse(status=401)

            request.audit_user = audit_user
            return fn(request, *args, **kwargs)
        return _inner
    return _outer
