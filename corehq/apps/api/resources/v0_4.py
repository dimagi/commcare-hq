
from tastypie import fields
from couchforms.models import XFormInstance

from corehq.apps.api.resources import v0_3
from corehq.apps.api.es import XFormES, ESQuerySet, es_search

class XFormInstanceResource(v0_3.XFormInstanceResource):

    # Some fields that were present when just fetching individual docs are
    # not present for e.g. devicelogs and must be allowed blank
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)

    def obj_get_list(self, request, domain, **kwargs):
        
        return ESQuerySet(payload = es_search(request, domain),
                          model = XFormInstance, 
                          es_client=XFormES(domain)) # Not that XFormES is used only as an ES client, for `run_query` against the proper index

    class Meta(v0_3.XFormInstanceResource.Meta):
        list_allowed_methods = ['get']
