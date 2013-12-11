from collections import namedtuple

from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.authorization import ReadOnlyAuthorization, Authorization
from tastypie.exceptions import BadRequest
from tastypie.throttle import CacheThrottle

from corehq.apps.users.models import CommCareUser, WebUser

from ..es import UserESMixin
from .v0_1 import UserResource, CustomResourceMeta
from . import JsonResource, DomainSpecificResourceMixin


class CommCareUserResource(UserESMixin, JsonResource, DomainSpecificResourceMixin):
    """
    A read-only user data resource based on elasticsearch.
    """
    # UserESMixin containst the logic for interacting with ES
    type = "user"
    id = fields.CharField(attribute='id', readonly=True, unique=True)
    username = fields.CharField(attribute='username', unique=True)
    first_name = fields.CharField(attribute='first_name', null=True)
    last_name = fields.CharField(attribute='last_name', null=True)
    email = fields.CharField(attribute='email')

    def to_obj(self, user):
        '''
        Takes a flat dict and returns an object
        '''
        user['id'] = user.pop('_id')
        return namedtuple('user', user.keys())(**user)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            user = self.Meta.object_class.get_by_user_id(pk, domain)
        except KeyError:
            user = None
        return user

    class Meta(CustomResourceMeta):
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        object_class = CommCareUser
        resource_name = 'user'

    def obj_get_list(self, bundle, **kwargs):
        print bundle.request.GET
        return map(self.to_obj, self.make_query())



