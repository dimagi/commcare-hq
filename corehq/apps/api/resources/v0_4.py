from django.core.urlresolvers import NoReverseMatch
from tastypie import fields
from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase

from corehq.apps.groups.models import Group
from corehq.apps.cloudcare.api import ElasticCaseQuery
from corehq.apps.api.resources.v0_2 import dict_object
from corehq.apps.api.resources import v0_3, JsonResource
from corehq.apps.api.es import XFormES, CaseES, ESQuerySet, es_search

class XFormInstanceResource(v0_3.XFormInstanceResource):

    # Some fields that were present when just fetching individual docs are
    # not present for e.g. devicelogs and must be allowed blank
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)

    # Prevent hitting Couch to md5 the attachment. However, there is no way to
    # eliminate a tastypie field defined in a parent class.
    md5 = fields.CharField(attribute='uiversion', blank=True, null=True)
    def dehydrate_md5(self, bundle):
        return 'OBSOLETED'

    def get_list(self, request, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.11/tastypie/resources.py#L1018
        (BSD licensed) and modified to pass the kwargs to `get_resource_list_uri`
        (tracked by https://github.com/toastdriven/django-tastypie/pull/815)
        """        
        objects = self.obj_get_list(request=request, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(request.GET, sorted_objects, resource_uri=self.get_resource_list_uri(request, **kwargs), limit=self._meta.limit)
        to_be_serialized = paginator.page()

        # Dehydrate the bundles in preparation for serialization.
        bundles = [self.build_bundle(obj=obj, request=request) for obj in to_be_serialized['objects']]
        to_be_serialized['objects'] = [self.full_dehydrate(bundle) for bundle in bundles]
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)

    def obj_get_list(self, request, domain, **kwargs):
        return ESQuerySet(payload = es_search(request, domain),
                          model = XFormInstance, 
                          es_client=XFormES(domain)) # Not that XFormES is used only as an ES client, for `run_query` against the proper index

    def get_resource_list_uri(self, request=None, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.11/tastypie/resources.py#L601
        (BSD licensed) and modified to use the kwargs
        """
        kwargs = dict(kwargs)
        kwargs['resource_name'] = self._meta.resource_name

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
            
        try:
            return self._build_reverse_url("api_dispatch_list", kwargs=kwargs)
        except NoReverseMatch:
            return None

    class Meta(v0_3.XFormInstanceResource.Meta):
        list_allowed_methods = ['get']

class CommCareCaseResource(v0_3.CommCareCaseResource):
    def get_list(self, request, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.11/tastypie/resources.py#L1018
        (BSD licensed) and modified to pass the kwargs to `get_resource_list_uri`
        (tracked by https://github.com/toastdriven/django-tastypie/pull/815)
        """        
        objects = self.obj_get_list(request=request, **self.remove_api_resource_names(kwargs))
        sorted_objects = self.apply_sorting(objects, options=request.GET)

        paginator = self._meta.paginator_class(request.GET, sorted_objects, resource_uri=self.get_resource_list_uri(request, **kwargs), limit=self._meta.limit)
        to_be_serialized = paginator.page()

        # Dehydrate the bundles in preparation for serialization.
        bundles = [self.build_bundle(obj=obj, request=request) for obj in to_be_serialized['objects']]
        to_be_serialized['objects'] = [self.full_dehydrate(bundle) for bundle in bundles]
        to_be_serialized = self.alter_list_data_to_serialize(request, to_be_serialized)
        return self.create_response(request, to_be_serialized)

    def get_resource_list_uri(self, request=None, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.11/tastypie/resources.py#L601
        (BSD licensed) and modified to use the kwargs
        """
        kwargs = dict(kwargs)
        kwargs['resource_name'] = self._meta.resource_name

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name
            
        try:
            return self._build_reverse_url("api_dispatch_list", kwargs=kwargs)
        except NoReverseMatch:
            return None

    def obj_get_list(self, request, domain, **kwargs):
        filters = v0_3.CaseListFilters(request.GET).filters
        return ESQuerySet(payload = ElasticCaseQuery(domain, filters).get_query(),
                          model = lambda jvalue: dict_object(CommCareCase.wrap(jvalue).get_json()),
                          es_client = CaseES(domain)) # Not that XFormES is used only as an ES client, for `run_query` against the proper index

class GroupResource(JsonResource):
    id = fields.CharField(attribute='get_id', unique=True, readonly=True)
    domain = fields.CharField(attribute='domain')
    name = fields.CharField(attribute='name')

    users = fields.ListField(attribute='get_user_ids')
    path = fields.ListField(attribute='path')

    case_sharing = fields.BooleanField(attribute='case_sharing', default=False)
    reporting = fields.BooleanField(default=True, attribute='reporting')

    metadata = fields.DictField(attribute='metadata')

    def obj_get_list(self, request, domain, **kwargs):
        groups = Group.by_domain(domain)
        return groups
        
    class Meta(v0_3.XFormInstanceResource.Meta):
        list_allowed_methods = ['get']
        resource_name = 'group'

