
from django.core.urlresolvers import NoReverseMatch
from tastypie import fields
from couchforms.models import XFormInstance

from corehq.apps.api.resources import v0_3
from corehq.apps.api.es import XFormES, ESQuerySet, es_search

class XFormInstanceResource(v0_3.XFormInstanceResource):

    # Some fields that were present when just fetching individual docs are
    # not present for e.g. devicelogs and must be allowed blank
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)

    def get_list(self, request, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.11/tastypie/resources.py#L1018
        (BSD licensed) and modified to pass the kwargs to `get_resource_list_uri`
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
