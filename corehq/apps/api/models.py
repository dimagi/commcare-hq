import os
from functools import wraps

from couchdbkit.exceptions import ResourceNotFound
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import check_password
from django.http import HttpResponse

from corehq.apps.api.resources import DictObject
from couchforms import const
from dimagi.ext.couchdbkit import *

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


class ESXFormInstance(DictObject):
    """This wrapper around form data returned from ES which
    provides attribute access and helper functions for
    the Form API.
    """

    @property
    def form_data(self):
        return self._data[const.TAG_FORM]

    @property
    def metadata(self):
        from corehq.form_processor.utils import clean_metadata
        from couchforms.models import Metadata
        if const.TAG_META in self.form_data:
            return Metadata.wrap(clean_metadata(self.form_data[const.TAG_META]))

        return None

    @property
    def is_archived(self):
        return self.doc_type == 'XFormArchived'

    @property
    def blobs(self):
        from corehq.blobs.mixin import BlobMeta
        blobs = {}
        if self._attachments:
            blobs.update({
                name: BlobMeta(
                    id=None,
                    content_length=info.get("length", None),
                    content_type=info.get("content_type", None),
                    digest=info.get("digest", None),
                ) for name, info in self._attachments.iteritems()
            })
        if self.external_blobs:
            blobs.update({
                name: BlobMeta.wrap(info)
                for name, info in self.external_blobs.iteritems()
            })

        return blobs

    @property
    def version(self):
        return self.form_data.get(const.TAG_VERSION, "")

    @property
    def uiversion(self):
        return self.form_data.get(const.TAG_UIVERSION, "")

    @property
    def type(self):
        return self.form_data.get(const.TAG_TYPE, "")

    @property
    def name(self):
        return self.form_data.get(const.TAG_NAME, "")
