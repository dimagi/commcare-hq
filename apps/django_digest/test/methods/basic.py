from base64 import b64encode

from django_digest.test.methods import WWWAuthenticateError, BaseAuth

class BasicAuth(BaseAuth):
    def authorization(self, request, response):
        if response is not None:
            challenges = self._authenticate_headers(response)
            if 'Basic' not in challenges:
                raise WWWAuthenticateError(
                    'Basic authentication unsupported for %s to %r.' %
                    (response.request['REQUEST_METHOD'],
                     response.request['PATH_INFO'])
                )
        return 'Basic %s' % b64encode(self.username + ':' +  self.password)
