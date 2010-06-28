from urllib import quote

from python_digest import build_authorization_request
from django_digest.test.methods import BaseAuth, WWWAuthenticateError


class DigestAuth(BaseAuth):
    def __init__(self, *args, **kwargs):
        super(DigestAuth, self).__init__(*args, **kwargs)
        self.nonce_count = 0
        self.digest_challenge = None

    def authorization(self, request, response):
        if response is not None:
            challenges = self._authenticate_headers(response)
            if 'Digest' not in challenges:
                raise WWWAuthenticateError(
                    'Digest authentication unsupported for %s to %r.' %
                    (response.request['REQUEST_METHOD'],
                     response.request['PATH_INFO'])
                )
            self.digest_challenge = challenges['Digest']
        elif self.digest_challenge is None:
            return
        self.nonce_count += 1
        return build_authorization_request(
            username=self.username,
            method=request['REQUEST_METHOD'],
            uri=quote(request['PATH_INFO']),
            nonce_count=self.nonce_count,
            digest_challenge=self.digest_challenge,
            password=self.password
        )
