import os
import re
from collections import defaultdict
from functools import wraps

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.http import HttpResponse

from couchforms import const

from corehq.apps.api.resources import DictObject
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex, XFormInstance
from corehq.form_processor.models.cases import CaseToXMLMixin, get_index_map

PERMISSION_POST_SMS = "POST_SMS"
PERMISSION_POST_WISEPILL = "POST_WISEPILL"


class ApiUser(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    password = models.CharField(max_length=255, null=True)
    permissions = ArrayField(
        models.CharField(max_length=126, null=True, blank=True),
        null=True,
        default=list
    )

    class Meta:
        db_table = "api_apiuser"

    @property
    def username(self):
        if self.id.startswith("ApiUser-"):
            return self.id[len("ApiUser-"):]
        else:
            raise Exception("ApiUser _id has to be 'ApiUser-' + username")

    def set_password(self, raw_password):
        salt = os.urandom(5).hex()
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
        self.id = "ApiUser-%s" % username
        self.set_password(password)
        self.permissions = permissions or []
        return self

    @classmethod
    def get_user(cls, username):
        return cls.objects.get(id="ApiUser-%s" % username)

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
        except ApiUser.DoesNotExist:
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
        if const.TAG_META in self.form_data:
            return clean_metadata(self.form_data[const.TAG_META])
        return None

    @property
    def is_archived(self):
        return self.doc_type == 'XFormArchived'

    @property
    def blobs(self):
        from corehq.blobs.mixin import BlobMetaRef
        blobs = {}
        if self._attachments:
            blobs.update({
                name: BlobMetaRef(
                    content_length=info.get("length", None),
                    content_type=info.get("content_type", None),
                ) for name, info in self._attachments.items()
            })
        if self.external_blobs:
            blobs.update({
                name: BlobMetaRef.wrap(info)
                for name, info in self.external_blobs.items()
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

    @property
    def server_modified_on(self):
        server_modified_on = self._data.get('server_modified_on', None)
        if not server_modified_on:
            server_modified_on = self._data.get('edited_on', None)
        if not server_modified_on:
            server_modified_on = self._data['received_on']
        return server_modified_on


class ESCase(DictObject, CaseToXMLMixin):
    """This wrapper around case data returned from ES which
    provides attribute access and helper functions for
    the Case API.
    """

    @property
    def case_id(self):
        return self._id

    @property
    def server_opened_on(self):
        try:
            open_action = self.actions[0]
            return open_action['server_date']
        except Exception:
            pass

    @property
    def indices(self):
        return [CommCareCaseIndex(**index) for index in self._data['indices'] if index["referenced_id"]]

    def get_index_map(self):
        return get_index_map(self.indices)

    def get_properties_in_api_format(self):
        return dict(list(self.dynamic_case_properties().items()) + list({
            "external_id": self.external_id,
            "owner_id": self.owner_id,
            # renamed
            "case_name": self.name,
            # renamed
            "case_type": self.type,
            # renamed
            "date_opened": self.opened_on,
            # all custom properties go here
        }.items()))

    def dynamic_case_properties(self):
        if self.case_json is not None:
            return self.case_json

        def is_dynamic(name, letterfirst=re.compile(r'^[a-zA-Z]')):
            return name not in CASE_PROPERTIES and letterfirst.search(name)
        return {k: v for k, v in sorted(self._data.items()) if is_dynamic(k)}

    @property
    def _reverse_indices(self):
        return CommCareCaseIndex.objects.get_all_reverse_indices_info(self.domain, [self._id])

    def get_forms(self):
        from corehq.apps.api.util import form_to_es_form
        forms = XFormInstance.objects.get_forms(self.xform_ids, self.domain)
        return list(filter(None, [form_to_es_form(form) for form in forms]))

    @property
    def child_cases(self):
        from corehq.apps.api.util import case_to_es_case
        return {
            index.case_id: case_to_es_case(
                CommCareCase.objects.get_case(index.case_id, self.domain))
            for index in self._reverse_indices
        }

    @property
    def parent_cases(self):
        from corehq.apps.api.util import case_to_es_case
        return {
            index.identifier: case_to_es_case(
                CommCareCase.objects.get_case(index.referenced_id, self.domain))
            for index in self.indices if index.referenced_id
        }

    @property
    def xforms_by_name(self):
        return _group_by_dict(self.get_forms(), lambda form: form.name)

    @property
    def xforms_by_xmlns(self):
        return _group_by_dict(self.get_forms(), lambda form: form.xmlns)


def _group_by_dict(objs, fn):
    """
    Itertools.groupby returns a transient iterator with alien
    data types in it. This returns a dictionary of lists.
    Less efficient but clients can write naturally and used
    only for things that have to fit in memory easily anyhow.
    """
    result = defaultdict(list)
    for obj in objs:

        key = fn(obj)
        result[key].append(obj)
    return result


CASE_PROPERTIES = {
    # CommCareCase.properties()
    '_attachments',
    '_id',
    '_rev',
    'actions',
    'case_attachments',
    'closed_by',
    'closed_on',
    'closed',
    'computed_',
    'computed_modified_on_',
    'doc_type',
    'domain',
    'export_tag',
    'external_blobs',
    'external_id',
    'indices',
    'initial_processing_complete'
    'modified_on',
    'name',
    'opened_by',
    'opened_on',
    'owner_id',
    'server_modified_on',
    'type',
    'user_id',
    'version',
    'xform_ids',

    # CommCareCase data descriptors
    # Derived from JsonObjectBase.__is_dynamic_property
    #
    # def is_data(name):
    #     return inspect.isdatadescriptor(getattr(CommCareCase, name))
    # {n for n in dir(CommCareCase) if is_data(n)} - CommCareCase.properties().keys()
    '_JsonObjectBase__dynamic_properties',
    '__weakref__',
    '_doc',
    '_dynamic_properties',
    'blobs',
    'case_id',
    'case_name',
    'deletion_date',
    'deletion_id',
    'get_id',
    'get_rev',
    'has_indices',
    'host',
    'is_deleted',
    'live_indices',
    'modified_by',
    'new_document',
    'parent',
    'persistent_blobs',
    'phone_sync_key',
    'raw_username',
    'reverse_indices',
    'server_opened_on',
}
