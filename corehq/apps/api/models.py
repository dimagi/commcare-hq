from couchdbkit.exceptions import ResourceNotFound
from couchdbkit.ext.django.schema import *

from django.contrib.auth.models import get_hexdigest, check_password
from django.http import HttpResponse
from django.conf import settings

PERMISSION_POST_SMS = "POST_SMS"

class ApiUser(Document):
    password = StringProperty()
    permissions = ListProperty(StringProperty)

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

    def has_permission(self, permission):
        return permission in self.permissions

    @classmethod
    def create(cls, username, password, permissions=None):
        """
        To create a new ApiUser on the server:
        ./manage.py shell

        $ from corehq.apps.api.models import *
        $ ApiUser.create('buildserver', 'RANDOM').save()
        
        """
        self = cls()
        self['_id'] = "ApiUser-%s" % username
        self.set_password(password)
        self.permissions = permissions or []
        return self

    @classmethod
    def get_user(cls, username):
        return cls.get("ApiUser-%s" % username)

    @classmethod
    def auth(cls, username, password, permission=None):
        try:
            user = cls.get_user(username)
            if user.check_password(password):
                if permission is not None:
                    return user.has_permission(permission)
                else:
                    return True
            else:
                return False
        except ResourceNotFound:
            return False

def _require_api_user(permission=None):
    def _outer2(fn):
        from django.views.decorators.http import require_POST
        if settings.DEBUG:
            return fn
        @require_POST
        def _outer(request, *args, **kwargs):
            if ApiUser.auth(request.POST.get('username', ''), request.POST.get('password', ''), permission):
                response = fn(request, *args, **kwargs)
            else:
                response = HttpResponse()
                response.status_code = 401
            return response
        return _outer
    return _outer2

require_api_user = _require_api_user()
require_api_user_permission = _require_api_user

