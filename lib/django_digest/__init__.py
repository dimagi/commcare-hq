import logging
import random
import time

from django.core import exceptions
        
from django.http import HttpRequest, HttpResponse
from django.utils.importlib import import_module

import python_digest

from django_digest.utils import get_backend, get_setting, DEFAULT_REALM

_l = logging.getLogger(__name__)

class DefaultLoginFactory(object):
    def confirmed_logins_for_user(self, user):
        return [login for login in
                [user.username, user.username.lower(), user.email,
                 user.email and user.email.lower()] if login]

    def unconfirmed_logins_for_user(self, user):
        return []

class HttpDigestAuthenticator(object):
    
    def __init__(self,
                 account_storage=None,
                 nonce_storage=None,
                 realm=None,
                 timeout=None,
                 enforce_nonce_count=None):
        if not enforce_nonce_count == None:
            self._enforce_nonce_count = enforce_nonce_count
        else:
            self._enforce_nonce_count = get_setting('DIGEST_ENFORCE_NONCE_COUNT', True)
        self.realm = realm or get_setting('DIGEST_REALM', DEFAULT_REALM)
        self.timeout = timeout or get_setting('DIGEST_NONCE_TIMEOUT_IN_SECONDS', 5*60)
        self._account_storage = (account_storage or get_backend(
                'DIGEST_ACCOUNT_BACKEND', 'django_digest.backend.db.AccountStorage'))
        self._nonce_storage = (nonce_storage or get_backend(
                'DIGEST_NONCE_BACKEND', 'django_digest.backend.db.NonceStorage'))
        self.secret_key = get_setting('SECRET_KEY')

    @staticmethod
    def contains_digest_credentials(request):
        return ('HTTP_AUTHORIZATION' in request.META and
                python_digest.is_digest_credential(request.META['HTTP_AUTHORIZATION']))

    def _store_nonce(self, user, nonce, nonce_count):
        if self._enforce_nonce_count:
            return self._nonce_storage.store_nonce(user, nonce, nonce_count)
        else:
            return self._nonce_storage.store_nonce(user, nonce, None)

    def _update_existing_nonce(self, user, nonce, nonce_count):
        if self._enforce_nonce_count:
            return self._nonce_storage.update_existing_nonce(user, nonce, nonce_count)
        else:
            return self._nonce_storage.update_existing_nonce(user, nonce, None)

    def authenticate(self, request):
        if not 'HTTP_AUTHORIZATION' in request.META:
            return False

        if not python_digest.is_digest_credential(request.META['HTTP_AUTHORIZATION']):
            return False

        digest_response = python_digest.parse_digest_credentials(
            request.META['HTTP_AUTHORIZATION'])

        if not digest_response:
            _l.debug('authentication failure: supplied digest credentials could not be ' \
                         'parsed: "%s".' % request.META['HTTP_AUTHORIZATION'])
            return False
        
        if not digest_response.realm == self.realm:
            _l.debug('authentication failure: supplied realm "%s" does not match ' \
                         'configured realm "%s".' % ( digest_response.realm, self.realm))
            return False

        if not python_digest.validate_nonce(digest_response.nonce, self.secret_key):
            _l.debug('authentication failure: nonce validation failed.')
            return False

        partial_digest = self._account_storage.get_partial_digest(digest_response.username)
        if not partial_digest:
            _l.debug('authentication failure: no partial digest available for user "%s".' \
                         % digest_response.username)
            return False

        calculated_request_digest = python_digest.calculate_request_digest(
            method=request.method, digest_response=digest_response,
            partial_digest=partial_digest)
        if not calculated_request_digest == digest_response.response:
            _l.debug('authentication failure: supplied request digest does not match ' \
                         'calculated request digest.')
            return False

        if not python_digest.validate_uri(digest_response.uri, request.path):
            _l.debug('authentication failure: digest authentication uri value "%s" does not ' \
                         'match value "%s" from HTTP request line.' % (digest_response.uri,
                                                                       request.path))
            return False

        user = self._account_storage.get_user(digest_response.username)

        if not self._update_existing_nonce(user, digest_response.nonce, digest_response.nc):
            if (python_digest.get_nonce_timestamp(digest_response.nonce) + self.timeout <
                time.time()):
                _l.debug('authentication failure: attempt to establish a new session with ' \
                             'a stale nonce.')
                return False

            if not self._store_nonce(user, digest_response.nonce, digest_response.nc):
                _l.debug('authentication failure: attempt to establish a previously used ' \
                             'or nonce count.')
                return False

        request.user = user
        return True
            
    def build_challenge_response(self, stale=False):
        response = HttpResponse('Authorization Required',
                                content_type='text/plain', status=401)
        opaque =  ''.join([random.choice('0123456789ABCDEF') for x in range(32)])

        response["WWW-Authenticate"] = python_digest.build_digest_challenge(
            time.time(), self.secret_key, self.realm, opaque, stale)
        return response
