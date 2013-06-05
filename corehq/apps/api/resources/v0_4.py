from django.core.urlresolvers import NoReverseMatch, reverse
from tastypie import fields
from tastypie.bundle import Bundle
from corehq.apps.api.util import get_object_or_not_exist

from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase

from corehq.apps.receiverwrapper.models import Repeater, repeater_types
from corehq.apps.groups.models import Group
from corehq.apps.cloudcare.api import ElasticCaseQuery
from corehq.apps.api.resources import v0_1, v0_3, JsonResource, DomainSpecificResourceMixin, dict_object
from corehq.apps.api.es import XFormES, CaseES, ESQuerySet, es_search
from corehq.apps.api.fields import ToManyDocumentsField

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.

MOCK_XFORM_ES = None

class XFormInstanceResource(v0_3.XFormInstanceResource, DomainSpecificResourceMixin):

    # Some fields that were present when just fetching individual docs are
    # not present for e.g. devicelogs and must be allowed blank
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)

    cases = ToManyDocumentsField('corehq.apps.api.resources.v0_4.CommCareCaseResource',
                                 attribute=lambda xform: None if 'case' not in xform.get_form else [dict_object(CommCareCase.get(xform.get_form['case']['@case_id']).get_json())])

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

class RepeaterResource(JsonResource, DomainSpecificResourceMixin):

    id = fields.CharField(attribute='_id', readonly=True, unique=True)
    type = fields.CharField(attribute='doc_type')
    domain = fields.CharField(attribute='domain')
    url = fields.CharField(attribute='url')
    version = fields.CharField(attribute='version', null=True)

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_list'):
        if isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None
        else:
            obj = bundle_or_obj

        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=obj.domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def obj_get_list(self, bundle, domain, **kwargs):
        repeaters = Repeater.by_domain(domain)
        return list(repeaters)

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Repeater, kwargs['pk'], kwargs['domain'],
                                       additional_doc_types=repeater_types.keys())

    def obj_create(self, bundle, request=None, **kwargs):
        bundle.obj.domain = kwargs['domain']
        bundle = self._update(bundle)
        bundle.obj.save()
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = Repeater.get(kwargs['pk'])
        assert bundle.obj.domain == kwargs['domain']
        bundle = self._update(bundle)
        assert bundle.obj.domain == kwargs['domain']
        bundle.obj.save()
        return bundle

    def _update(self, bundle):
        for key, value in bundle.data.items():
            setattr(bundle.obj, key, value)
        bundle = self.full_hydrate(bundle)
        return bundle

    class Meta(v0_1.CustomResourceMeta):
        object_class = Repeater
        resource_name = 'data-forwarding'
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']
        authorization = v0_1.DomainAdminAuthorization

class CommCareCaseResource(v0_3.CommCareCaseResource, DomainSpecificResourceMixin):
    def obj_get_list(self, bundle, domain, **kwargs):
        filters = v0_3.CaseListFilters(bundle.request.GET).filters

        # Since tastypie handles the "from" and "size" via slicing, we have to wipe them out here
        # since ElasticCaseQuery adds them. I believe other APIs depend on the behavior of ElasticCaseQuery
        # hence I am not modifying that
        query = ElasticCaseQuery(domain, filters).get_query()
        if 'from' in query:
            del query['from']
        if 'size' in query:
            del query['size']
        
        return ESQuerySet(payload = query,
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

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Group, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        groups = Group.by_domain(domain)
        return groups
        
    class Meta(v0_3.XFormInstanceResource.Meta):
        object_class = Group    
        list_allowed_methods = ['get']
        resource_name = 'group'

