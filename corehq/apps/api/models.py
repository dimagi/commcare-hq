from functools import wraps
from couchdbkit.exceptions import ResourceNotFound
from dimagi.ext.couchdbkit import *

from django.contrib.auth.models import check_password
from django.http import HttpResponse
from django.conf import settings

import os
from corehq.util.hash_compat import make_password

PERMISSION_POST_SMS = "POST_SMS"
PERMISSION_POST_WISEPILL = "POST_WISEPILL"

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
        salt = os.urandom(5).encode('hex')
        self.password = make_password(raw_password, salt=salt)

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
        @wraps(fn)
        def _outer(request, *args, **kwargs):
            if ApiUser.auth(request.POST.get('username', ''), request.POST.get('password', ''), permission):
                response = fn(request, *args, **kwargs)
            else:
                response = HttpResponse(status=401)
            return response
        return _outer
    return _outer2

require_api_user = _require_api_user()
require_api_user_permission = _require_api_user

