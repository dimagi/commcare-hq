from collections import defaultdict

from django.core.urlresolvers import NoReverseMatch, reverse
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest
from tastypie import fields
from tastypie.bundle import Bundle
from tastypie.authentication import Authentication

from couchforms.models import XFormInstance
from casexml.apps.case.models import CommCareCase
from casexml.apps.case import xform as casexml_xform
from custom.hope.models import HOPECase

from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.app_manager import util as app_manager_util
from corehq.apps.app_manager.models import ApplicationBase, Application, RemoteApp, Form, get_app
from corehq.apps.receiverwrapper.models import Repeater, repeater_types
from corehq.apps.groups.models import Group
from corehq.apps.cloudcare.api import ElasticCaseQuery
from corehq.apps.users.util import format_username
from corehq.apps.users.models import CouchUser, CommCareUser

from corehq.apps.api.resources import v0_1, v0_3, JsonResource, DomainSpecificResourceMixin, dict_object, SimpleSortableResourceMixin
from corehq.apps.api.es import XFormES, CaseES, ESQuerySet, es_search
from corehq.apps.api.fields import ToManyDocumentsField, UseIfRequested, ToManyDictField, ToManyListDictField, CallableCharField
from corehq.apps.api.serializers import CommCareCaseSerializer

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.

MOCK_XFORM_ES = None
MOCK_CASE_ES = None

class XFormInstanceResource(SimpleSortableResourceMixin, v0_3.XFormInstanceResource, DomainSpecificResourceMixin):

    # Some fields that were present when just fetching individual docs are
    # not present for e.g. devicelogs and must be allowed blank
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)
    domain = fields.CharField(attribute='domain')

    cases = UseIfRequested(ToManyDocumentsField('corehq.apps.api.resources.v0_4.CommCareCaseResource',
                                                attribute=lambda xform: [dict_object(case.get_json()) for case in casexml_xform.cases_referenced_by_xform(xform)]))

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

        # Note that XFormES is used only as an ES client, for `run_query` against the proper index
        return ESQuerySet(payload = es_query,
                          model = XFormInstance, 
                          es_client=self.xform_es(domain)).order_by('-received_on')

    class Meta(v0_3.XFormInstanceResource.Meta):
        ordering = ['received_on']
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

def group_by_dict(objs, fn):
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


class CommCareCaseResource(SimpleSortableResourceMixin, v0_3.CommCareCaseResource, DomainSpecificResourceMixin):

    xforms_by_name = UseIfRequested(ToManyListDictField(
        'corehq.apps.api.resources.v0_4.XFormInstanceResource',
        attribute=lambda case: group_by_dict(case.get_forms(), lambda form: form.name)
    ))

    xforms_by_xmlns = UseIfRequested(ToManyListDictField(
        'corehq.apps.api.resources.v0_4.XFormInstanceResource',
        attribute=lambda case: group_by_dict(case.get_forms(), lambda form: form.xmlns)
    ))

    child_cases = UseIfRequested(ToManyDictField('corehq.apps.api.resources.v0_4.CommCareCaseResource',
                                                 attribute=lambda case: dict([ (index.identifier, CommCareCase.get(index.referenced_id)) for index in case.indices])))

    parent_cases = UseIfRequested(ToManyDictField('corehq.apps.api.resources.v0_4.CommCareCaseResource',
                                                  attribute=lambda case: dict([ (index.identifier, CommCareCase.get(index.referenced_id)) for index in case.reverse_indices])))

    domain = fields.CharField(attribute='domain')

    # Fields that v0.2 assumed were pre-transformed but we are now operating on straight CommCareCase objects again
    date_modified = fields.CharField(attribute='modified_on', default="1900-01-01")
    server_date_modified = fields.CharField(attribute='server_modified_on', default="1900-01-01")

    def case_es(self, domain):
        return MOCK_CASE_ES or CaseES(domain)

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
                          model = CommCareCase,
                          es_client = self.case_es(domain)).order_by('server_modified_on') # Not that CaseES is used only as an ES client, for `run_query` against the proper index

    class Meta(v0_3.CommCareCaseResource.Meta):
        max_limit = 100 # Today, takes ~25 seconds for some domains
        serializer = CommCareCaseSerializer()
        ordering = ['server_date_modified', 'date_modified']


class GroupResource(JsonResource, DomainSpecificResourceMixin):
    id = fields.CharField(attribute='get_id', unique=True, readonly=True)
    domain = fields.CharField(attribute='domain')
    name = fields.CharField(attribute='name')

    users = fields.ListField(attribute='get_user_ids')
    path = fields.ListField(attribute='path')

    case_sharing = fields.BooleanField(attribute='case_sharing', default=False)
    reporting = fields.BooleanField(default=True, attribute='reporting')

    metadata = fields.DictField(attribute='metadata', null=True, blank=True)

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Group, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        groups = Group.by_domain(domain)
        return groups
        
    class Meta(v0_3.XFormInstanceResource.Meta):
        object_class = Group    
        list_allowed_methods = ['get']
        resource_name = 'group'

    
class SingleSignOnResource(JsonResource, DomainSpecificResourceMixin):
    """
    This resource does not require "authorization" per se, but
    rather allows a POST of username and password and returns
    just the authenticated user, if the credentials and domain
    are correct.
    """

    def post_list(self, request, **kwargs):
        domain = kwargs.get('domain')
        request.domain = domain
        username = request.POST.get('username')
        password = request.POST.get('password')

        if username is None:
            return HttpResponseBadRequest('Missing required parameter: username')

        if password is None:
            return HttpResponseBadRequest('Missing required parameter: password')

        if '@' not in username:
            username = format_username(username, domain)

        # Convert to the appropriate type of user
        couch_user = CouchUser.get_by_username(username)
        if couch_user is None or not couch_user.is_member_of(domain) or not couch_user.check_password(password):
            return HttpResponseForbidden()

        if couch_user.is_commcare_user():
            user_resource = v0_1.CommCareUserResource()
        elif couch_user.is_web_user():
            user_resource = v0_1.WebUserResource()
        else:
            return HttpResponseForbidden()
        
        bundle = user_resource.build_bundle(obj=couch_user, request=request)
        bundle = user_resource.full_dehydrate(bundle)
        return user_resource.create_response(request, bundle, response_class=HttpResponse)

    def get_list(self, bundle, **kwargs):
        return HttpResponseForbidden()

    def get_detail(self, bundle, **kwargs):
        return HttpResponseForbidden()

    class Meta(v0_1.CustomResourceMeta):
        authentication = Authentication() 
        resource_name = 'sso'
        detail_allowed_methods = []
        list_allowed_methods = ['post']


class ApplicationResource(JsonResource, DomainSpecificResourceMixin):

    name = fields.CharField(attribute='name')

    modules = fields.ListField()
    def dehydrate_module(self, app, module, langs):
        """
        Convert a Module object to a JValue representation
        with just the good parts.

        NOTE: This is not a tastypie "magic"-name method to
        dehydrate the "module" field; there is no such field.
        """
        dehydrated = {}

        dehydrated['case_type'] = module.case_type

        dehydrated['case_properties'] = app_manager_util.get_case_properties(app, [module.case_type], defaults=['name'])[module.case_type]
        
        dehydrated['forms'] = []
        for form in module.forms:
            form = Form.get_form(form.unique_id)
            form_jvalue = {
                'xmlns': form.xmlns,
                'name': form.name,
                'questions': form.get_questions(langs),
            }
            dehydrated['forms'].append(form_jvalue)

        return dehydrated
    
    def dehydrate_modules(self, bundle):
        app = bundle.obj

        if app.doc_type == Application._doc_type:
            return [self.dehydrate_module(app, module, app.langs) for module in bundle.obj.modules]
        elif app.doc_type == RemoteApp._doc_type:
            return []

    def obj_get_list(self, bundle, domain, **kwargs):
        # There should be few enough apps per domain that doing an explicit refresh for each is OK.
        # This is the easiest way to filter remote apps
        # Later we could serialize them to their URL or whatevs but it is not that useful yet

        application_bases = ApplicationBase.by_domain(domain)

        # This wraps in the appropriate class so that is_remote_app() returns the correct answer 
        applications = [get_app(domain, application_base.id) for application_base in application_bases]
        
        return [app for app in applications if not app.is_remote_app()]

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Application, kwargs['domain'], kwargs['pk'])

    class Meta(v0_1.CustomResourceMeta):
        object_class = Application
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'application'

def bool_to_yesno(value):
    if value is None:
        return None
    elif value:
        return 'yes'
    else:
        return 'no'

def get_yesno(attribute):
    return lambda obj: bool_to_yesno(getattr(obj, attribute, None))

class HOPECaseResource(CommCareCaseResource):
    """
    Custom API endpoint for custom case wrapper
    """

    # For the curious, the attribute='<exact thing I just typed>' is mandatory,
    # and refers to a property on the HOPECase object
    all_anc_doses_given = fields.CharField(attribute='_HOPE_all_anc_doses_given', readonly=True, null=True)
    all_dpt1_opv1_hb1_doses_given = CallableCharField(attribute=get_yesno('_HOPE_all_dpt1_opv1_hb1_doses_given'),
                                                     readonly=True, null=True)
    all_dpt2_opv2_hb2_doses_given = CallableCharField(attribute=get_yesno('_HOPE_all_dpt2_opv2_hb2_doses_given'),
                                                     readonly=True, null=True)
    all_dpt3_opv3_hb3_doses_given = CallableCharField(attribute=get_yesno('_HOPE_all_dpt3_opv3_hb3_doses_given'),
                                                     readonly=True, null=True)
    all_ifa_doses_given = CallableCharField(attribute=get_yesno('_HOPE_all_ifa_doses_given'),
                                           readonly=True, null=True)
    all_tt_doses_given = CallableCharField(attribute=get_yesno('_HOPE_all_tt_doses_given'),
                                          readonly=True, null=True)
    asha_id = fields.CharField(attribute='_HOPE_asha_id', readonly=True, null=True)
    bcg_indicator = fields.BooleanField(attribute='_HOPE_bcg_indicator', readonly=True, null=True)
    child_name = fields.CharField(attribute='_HOPE_child_name', readonly=True, null=True)
    delivery_nature = fields.CharField(attribute='_HOPE_delivery_nature', readonly=True, null=True)
    delivery_type = fields.CharField(attribute='_HOPE_delivery_type', readonly=True, null=True)
    dpt_1_indicator = fields.BooleanField(attribute='_HOPE_dpt_1_indicator', readonly=True, null=True)
    existing_child_count = fields.IntegerField(attribute='_HOPE_existing_child_count', readonly=True, null=True)
    ifa1_date = fields.CharField(attribute='_HOPE_ifa1_date', readonly=True, null=True)
    ifa2_date = fields.CharField(attribute='_HOPE_ifa2_date', readonly=True, null=True)
    ifa3_date = fields.CharField(attribute='_HOPE_ifa3_date', readonly=True, null=True)
    measles_dose_given = CallableCharField(attribute=get_yesno('_HOPE_measles_dose_given'),
                                          readonly=True, null=True)
    number_of_visits = fields.IntegerField(attribute='_HOPE_number_of_visits', readonly=True, null=True)
    opv_1_indicator = fields.BooleanField(attribute='_HOPE_opv_1_indicator', readonly=True, null=True)
    registration_date = fields.CharField(attribute='_HOPE_registration_date', readonly=True, null=True)
    tubal_ligation = fields.BooleanField(attribute='_HOPE_tubal_ligation', readonly=True, null=True)

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(HOPECase, kwargs['pk'], kwargs['domain'],
                                       additional_doc_types=['CommCareCase'])

    def obj_get_list(self, bundle, domain, **kwargs):
        """
        Overridden to wrap the case JSON from ElasticSearch with the custom.hope.case.HOPECase class
        """
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
                          model = HOPECase,
                          es_client = self.case_es(domain)).order_by('server_modified_on') # Not that CaseES is used only as an ES client, for `run_query` against the proper index

    class Meta(CommCareCaseResource.Meta):
        resource_name = 'hope-case'



