from django.core.urlresolvers import NoReverseMatch
from tastypie import fields

from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase

from corehq.apps.groups.models import Group
from corehq.apps.cloudcare.api import ElasticCaseQuery
from corehq.apps.api.resources import v0_3, JsonResource, DomainSpecificResourceMixin, dict_object
from corehq.apps.api.es import XFormES, CaseES, ESQuerySet, es_search

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.

MOCK_XFORM_ES = None

class XFormInstanceResource(v0_3.XFormInstanceResource, DomainSpecificResourceMixin):

    # Some fields that were present when just fetching individual docs are
    # not present for e.g. devicelogs and must be allowed blank
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)

    # Prevent hitting Couch to md5 the attachment. However, there is no way to
    # eliminate a tastypie field defined in a parent class.
    md5 = fields.CharField(attribute='uiversion', blank=True, null=True)
    def dehydrate_md5(self, bundle):
        return 'OBSOLETED'

    def xform_es(self, domain):
        return MOCK_XFORM_ES or XFormES(domain)

    def obj_get_list(self, bundle, domain, **kwargs):
        es_query = es_search(bundle.request, domain)    
        es_query['filter']['and'].append({'term': {'doc_type': 'xforminstance'}})

        return ESQuerySet(payload = es_query,
                          model = XFormInstance, 
                          es_client=self.xform_es(domain)) # Not that XFormES is used only as an ES client, for `run_query` against the proper index

    class Meta(v0_3.XFormInstanceResource.Meta):
        list_allowed_methods = ['get']

class CommCareCaseResource(v0_3.CommCareCaseResource, DomainSpecificResourceMixin):
    def obj_get_list(self, bundle, domain, **kwargs):
        filters = v0_3.CaseListFilters(bundle.request.GET).filters
        return ESQuerySet(payload = ElasticCaseQuery(domain, filters).get_query(),
                          model = lambda jvalue: dict_object(CommCareCase.wrap(jvalue).get_json()),
                          es_client = CaseES(domain)) # Not that XFormES is used only as an ES client, for `run_query` against the proper index

class GroupResource(JsonResource, DomainSpecificResourceMixin):
    id = fields.CharField(attribute='get_id', unique=True, readonly=True)
    domain = fields.CharField(attribute='domain')
    name = fields.CharField(attribute='name')

    users = fields.ListField(attribute='get_user_ids')
    path = fields.ListField(attribute='path')

    case_sharing = fields.BooleanField(attribute='case_sharing', default=False)
    reporting = fields.BooleanField(default=True, attribute='reporting')

    metadata = fields.DictField(attribute='metadata')

    def obj_get_list(self, bundle, domain, **kwargs):
        groups = Group.by_domain(domain)
        return groups
        
    class Meta(v0_3.XFormInstanceResource.Meta):
        object_class = Group    
        list_allowed_methods = ['get']
        resource_name = 'group'

