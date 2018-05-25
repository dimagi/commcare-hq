from __future__ import absolute_import
from __future__ import unicode_literals
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
    location_safe, LOCATION_ACCESS_DENIED, user_can_view_location, user_can_edit_location)
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
    have_access_to_parent = fields.BooleanField(readonly=True)

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
            locs = SQLLocation.root_locations(domain, include_inactive)
        else:
            parent = get_location_or_not_exist(parent_id, domain)
            if not user_can_view_location(user, parent, project):
                raise BadRequest(LOCATION_ACCESS_DENIED)
            locs = self.child_queryset(domain, include_inactive, parent)
        return [
            child for child in locs if user_can_view_location(user, child, project) or
            user_can_access_location_id(project, user, child.location_id)
        ]

    def dehydrate_can_edit(self, bundle):
        project = getattr(bundle.request, 'project', self.domain_obj(bundle.request.domain))
        return user_can_edit_location(bundle.request.couch_user, bundle.obj, project)

    def dehydrate_have_access_to_parent(self, bundle):
        project = getattr(bundle.request, 'project', self.domain_obj(bundle.request.domain))
        parent_id = bundle.request.GET.get('parent_id', None)
        if parent_id is None:
            return False
        return user_can_access_location_id(project, bundle.request.couch_user, parent_id)

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
