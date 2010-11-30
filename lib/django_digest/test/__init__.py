import django.test

from django_digest.test.methods.basic import BasicAuth
from django_digest.test.methods.detect import DetectAuth
from django_digest.test.methods.digest import DigestAuth

class Client(django.test.Client):
    AUTH_METHODS = {'Basic': BasicAuth,
                    'Digest': DigestAuth}

    def __init__(self, *args, **kwargs):
        super(Client, self).__init__(*args, **kwargs)
        self.clear_authorization()

    def request(self, **request):
        if self.auth_method:
            request.update(self.auth_method(request))
        response = super(Client, self).request(**request)
        if response.status_code == 401 and self.auth_method:
            # Try to authenticate
            request.update(self.auth_method(request, response))
            response = super(Client, self).request(**request)
        return response

    def set_authorization(self, username, password, method=None):
        self.username = username
        self.password = password
        if method is None:
            self.auth_method = DetectAuth(client=self,
                                          username=username,
                                          password=password)
        else:
            self.auth_method = self.AUTH_METHODS[method](username=username,
                                                         password=password)

    def clear_authorization(self):
        self.username = None
        self.password = None
        self.auth_method = None
