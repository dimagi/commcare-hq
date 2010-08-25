from django_digest.test.methods import BaseAuth, WWWAuthenticateError

class DetectAuth(BaseAuth):
    def __init__(self, client, *args, **kwargs):
        super(DetectAuth, self).__init__(*args, **kwargs)
        self.client = client
        self.selected_method = None

    def authorization(self, request, response):
        if self.selected_method is None:
            if response is None or response.status_code != 401:
                # we haven't previously authenticated, and we don't need to (or don't
                # know that we need to)
                return None
            
            challenges = self._authenticate_headers(response)
            for method, challenge in challenges.iteritems():
                # Loop through possible challenges to find the first one we
                # can handle.
                if method not in self.client.AUTH_METHODS:
                    continue
                self.selected_method = self.client.AUTH_METHODS[method](username=self.username,
                                                                        password=self.password)
                break

        if self.selected_method is None:
            raise WWWAuthenticateError(
                '%r authentication methods unsupported for %s to %r.' %
                (tuple(self.client.AUTH_METHODS),
                 response.request['REQUEST_METHOD'], response.request['PATH_INFO'])
                )

        return self.selected_method.authorization(request, response)
