import json
from tastypie import fields
from tastypie.exceptions import BadRequest
from tastypie.resources import Resource

from corehq.apps.api.resources.auth import LoginAndDomainAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import object_does_not_exist
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.domain.models import Domain
from corehq.apps.locations.permissions import (
    location_safe, LOCATION_ACCESS_DENIED)
from corehq.apps.users.models import WebUser
from corehq.util.quickcache import quickcache
from memoized import memoized

from ..models import SQLLocation
from ..permissions import user_can_access_location_id


def get_location_or_not_exist(location_id, domain):
    try:
        return SQLLocation.objects.get(location_id=location_id, domain=domain)
    except SQLLocation.DoesNotExist:
        raise object_does_not_exist('Location', location_id)


@location_safe
class LocationResource(HqBaseResource):
    type = "location"
    uuid = fields.CharField(attribute='location_id', readonly=True, unique=True)
    location_type = fields.CharField(attribute='location_type', readonly=True)
    is_archived = fields.BooleanField(attribute='is_archived', readonly=True)
    can_edit = fields.BooleanField(readonly=True)
    name = fields.CharField(attribute='name', readonly=True, unique=True)

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        location_id = kwargs['pk']
        if not user_can_access_location_id(domain, bundle.request.couch_user, location_id):
            raise BadRequest(LOCATION_ACCESS_DENIED)
        return get_location_or_not_exist(location_id, domain)

    def child_queryset(self, domain, include_inactive, parent):
        return parent.sql_location.child_locations(include_inactive)

    @memoized
    def domain_obj(self, domain_name):
        return Domain.get_by_name(domain_name)

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        project = getattr(bundle.request, 'project', self.domain_obj(domain))
        parent_id = bundle.request.GET.get('parent_id', None)
        include_inactive = json.loads(bundle.request.GET.get('include_inactive', 'false'))
        user = bundle.request.couch_user

        if not parent_id:
            if not user.has_permission(domain, 'access_all_locations'):
                raise BadRequest(LOCATION_ACCESS_DENIED)
            return SQLLocation.root_locations(domain, include_inactive)
        else:
            if not user_can_access_location_id(kwargs['domain'], user, parent_id):
                raise BadRequest(LOCATION_ACCESS_DENIED)
            parent = get_location_or_not_exist(parent_id, domain)
            return self.child_queryset(domain, include_inactive, parent)

    def dehydrate_can_edit(self, bundle):
        # This is a relic of times past; if you can see a location, you can edit it
        return True

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication()
        object_class = SQLLocation
        resource_name = 'location'
        limit = 0
        max_limit = 10000


@location_safe
class InternalLocationResource(LocationResource):

    # using the default resource dispatch function to bypass our authorization for internal use
    def dispatch(self, request_type, request, **kwargs):
        return Resource.dispatch(self, request_type, request, **kwargs)

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication(allow_session_auth=True)
        object_class = SQLLocation
        resource_name = 'location_internal'
        limit = 0
        max_limit = 10000
