from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *

from django.contrib.auth.models import get_hexdigest, check_password
from django.http import HttpResponse
import settings

class ApiUser(Document):
    password = StringProperty()

    @property
    def username(self):
        if self['_id'].startswith("ApiUser-"):
            return self['_id'][len("ApiUser-"):]
        else:
            raise Exception("ApiUser _id has to be 'ApiUser-' + username")

    def set_password(self, raw_password):
        import random
        algo = 'sha1'
        salt = get_hexdigest(algo, str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(algo, salt, raw_password)
        self.password = '%s$%s$%s' % (algo, salt, hsh)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    @classmethod
    def create(cls, username, password):
        """
        To create a new ApiUser on the server:
        ./manage.py shell

        $ from corehq.apps.api.models import *
        $ ApiUser.create('buildserver', 'RANDOM').save()
        
        """
        self = cls()
        self['_id'] = "ApiUser-%s" % username
        self.set_password(password)
        return self

    @classmethod
    def get_user(cls, username):
        return cls.get("ApiUser-%s" % username)

    @classmethod
    def auth(cls, username, password):
        try:
            return cls.get_user(username).check_password(password)
        except ResourceNotFound:
            return False

def require_api_user(fn):
    from django.views.decorators.http import require_POST
    if settings.DEBUG:
        return fn
    @require_POST
    def _outer(request, *args, **kwargs):
        if ApiUser.auth(request.POST.get('username', ''), request.POST.get('password', '')):
            response = fn(request, *args, **kwargs)
        else:
            response = HttpResponse()
            response.status_code = 401
        return response
    return _outer
