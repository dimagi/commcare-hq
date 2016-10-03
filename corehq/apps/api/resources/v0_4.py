from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest
from tastypie import fields
from tastypie.bundle import Bundle
from tastypie.authentication import Authentication
from tastypie.exceptions import BadRequest

from corehq.apps.api.models import ESXFormInstance, ESCase
from corehq.apps.api.resources.auth import DomainAdminAuthentication, RequirePermissionAuthentication
from corehq.apps.api.resources.v0_1 import _safe_bool
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.form_processor.exceptions import XFormNotFound, CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from couchforms.models import doc_types
from casexml.apps.case import xform as casexml_xform
from custom.hope.models import HOPECase, CC_BIHAR_NEWBORN, CC_BIHAR_PREGNANCY

from corehq.apps.api.util import get_object_or_not_exist, object_does_not_exist, get_obj, form_to_es_form, \
    case_to_es_case
from corehq.apps.app_manager import util as app_manager_util
from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.repeaters.models import Repeater
from corehq.apps.repeaters.utils import get_all_repeater_types
from corehq.apps.groups.models import Group
from corehq.apps.cloudcare.api import ElasticCaseQuery
from corehq.apps.users.util import format_username
from corehq.apps.users.models import CouchUser, Permissions

from corehq.apps.api.resources import (
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
    SimpleSortableResourceMixin,
    v0_1,
    v0_3,
)
from corehq.apps.api.es import XFormES, CaseES, ElasticAPIQuerySet, es_search
from corehq.apps.api.fields import ToManyDocumentsField, UseIfRequested, ToManyDictField, ToManyListDictField
from corehq.apps.api.serializers import CommCareCaseSerializer, XFormInstanceSerializer

from no_exceptions.exceptions import Http400

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.
MOCK_XFORM_ES = None
MOCK_CASE_ES = None

xform_doc_types = doc_types()


class XFormInstanceResource(SimpleSortableResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    """This version of the form resource is built of Elasticsearch data
    which gets wrapped by ``ESXFormInstance``.
    No type conversion is done e.g. dates and some fields are named differently than in the
    Python models.
    """

    id = fields.CharField(attribute='_id', readonly=True, unique=True)

    domain = fields.CharField(attribute='domain')
    form = fields.DictField(attribute='form_data')
    type = fields.CharField(attribute='type')
    version = fields.CharField(attribute='version')
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)
    received_on = fields.CharField(attribute="received_on")

    app_id = fields.CharField(attribute='app_id', null=True)
    build_id = fields.CharField(attribute='build_id', null=True)
    initial_processing_complete = fields.BooleanField(
        attribute='initial_processing_complete', null=True)
    problem = fields.CharField(attribute='problem', null=True)

    archived = fields.CharField(readonly=True)

    def dehydrate_archived(self, bundle):
        return bundle.obj.is_archived

    cases = UseIfRequested(
        ToManyDocumentsField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute=lambda xform: casexml_xform.cases_referenced_by_xform(xform)
        )
    )

    attachments = fields.DictField(readonly=True, null=True)

    def dehydrate_attachments(self, bundle):
        attachments_dict = getattr(bundle.obj, 'blobs', None)
        if not attachments_dict:
            return {}

        def _normalize_meta(meta):
            return {
                'content_type': meta.content_type,
                'length': meta.content_length,
            }

        return {
            name: _normalize_meta(meta) for name, meta in attachments_dict.items()
        }

    is_phone_submission = fields.BooleanField(readonly=True)

    def dehydrate_is_phone_submission(self, bundle):
        return (
            getattr(bundle.obj, 'openrosa_headers', None)
            and bundle.obj.openrosa_headers.get('HTTP_X_OPENROSA_VERSION')
        )

    def obj_get(self, bundle, **kwargs):
        instance_id = kwargs['pk']
        try:
            form = FormAccessors(kwargs['domain']).get_form(instance_id)
            es_form = form_to_es_form(form)
            if es_form:
                return es_form
            else:
                raise XFormNotFound
        except XFormNotFound:
            raise object_does_not_exist("XFormInstance", instance_id)

    def xform_es(self, domain):
        return MOCK_XFORM_ES or XFormES(domain)

    def obj_get_list(self, bundle, domain, **kwargs):
        include_archived = 'include_archived' in bundle.request.GET
        try:
            es_query = es_search(bundle.request, domain, ['include_archived'])
        except Http400 as e:
            raise BadRequest(e.message)
        if include_archived:
            es_query['filter']['and'].append({'or': [
                {'term': {'doc_type': 'xforminstance'}},
                {'term': {'doc_type': 'xformarchived'}},
            ]})
        else:
            es_query['filter']['and'].append({'term': {'doc_type': 'xforminstance'}})

        # Note that XFormES is used only as an ES client, for `run_query` against the proper index
        return ElasticAPIQuerySet(
            payload=es_query,
            model=ESXFormInstance,
            es_client=self.xform_es(domain)
        ).order_by('-received_on')

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).form_id
        }

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        object_class = ESXFormInstance
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'form'
        ordering = ['received_on']
        serializer = XFormInstanceSerializer(formats=['json'])


class RepeaterResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):

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
                                       additional_doc_types=get_all_repeater_types().keys())

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

    class Meta(CustomResourceMeta):
        authentication = DomainAdminAuthentication()
        object_class = Repeater
        resource_name = 'data-forwarding'
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']


class CommCareCaseResource(SimpleSortableResourceMixin, v0_3.CommCareCaseResource, DomainSpecificResourceMixin):
    xforms_by_name = UseIfRequested(ToManyListDictField(
        'corehq.apps.api.resources.v0_4.XFormInstanceResource',
        attribute='xforms_by_name'
    ))

    xforms_by_xmlns = UseIfRequested(ToManyListDictField(
        'corehq.apps.api.resources.v0_4.XFormInstanceResource',
        attribute='xforms_by_xmlns'
    ))

    child_cases = UseIfRequested(
        ToManyDictField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute='child_cases'
        )
    )

    parent_cases = UseIfRequested(
        ToManyDictField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute='parent_cases'
        )
    )

    domain = fields.CharField(attribute='domain')

    # Fields that v0.2 assumed were pre-transformed but we are now operating on straight CommCareCase objects again
    date_modified = fields.CharField(attribute='modified_on', default="1900-01-01")
    server_date_modified = fields.CharField(attribute='server_modified_on', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_opened_on', default="1900-01-01")

    def obj_get(self, bundle, **kwargs):
        case_id = kwargs['pk']
        try:
            case = CaseAccessors(kwargs['domain']).get_case(case_id)
            return case_to_es_case(case)
        except CaseNotFound:
            raise object_does_not_exist("CommCareCase", case_id)

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

        # Note that CaseES is used only as an ES client, for `run_query` against the proper index
        return ElasticAPIQuerySet(
            payload=query,
            model=ESCase,
            es_client=self.case_es(domain)
        ).order_by('server_modified_on')

    class Meta(v0_3.CommCareCaseResource.Meta):
        max_limit = 1000
        serializer = CommCareCaseSerializer()
        ordering = ['server_date_modified', 'date_modified']
        object_class = ESCase


class GroupResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
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

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_commcare_users)
        object_class = Group
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'group'


class SingleSignOnResource(HqBaseResource, DomainSpecificResourceMixin):
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

    class Meta(CustomResourceMeta):
        authentication = Authentication()
        resource_name = 'sso'
        detail_allowed_methods = []
        list_allowed_methods = ['post']


class ApplicationResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):

    id = fields.CharField(attribute='_id')
    name = fields.CharField(attribute='name')
    version = fields.IntegerField(attribute='version')
    modules = fields.ListField()

    def dehydrate_module(self, app, module, langs):
        """
        Convert a Module object to a JValue representation
        with just the good parts.

        NOTE: This is not a tastypie "magic"-name method to
        dehydrate the "module" field; there is no such field.
        """
        try:
            dehydrated = {}

            dehydrated['case_type'] = module.case_type

            dehydrated['case_properties'] = app_manager_util.get_case_properties(
                app, [module.case_type], defaults=['name']
            )[module.case_type]

            dehydrated['unique_id'] = module.unique_id

            dehydrated['forms'] = []
            for form in module.forms:
                form_unique_id = form.unique_id
                form_jvalue = {
                    'xmlns': form.xmlns,
                    'name': form.name,
                    'questions': form.get_questions(langs, include_translations=True),
                    'unique_id': form_unique_id,
                }
                dehydrated['forms'].append(form_jvalue)
            return dehydrated
        except Exception as e:
            return {
                'error': unicode(e)
            }

    def dehydrate_modules(self, bundle):
        app = bundle.obj

        if app.doc_type == Application._doc_type:
            return [self.dehydrate_module(app, module, app.langs) for module in bundle.obj.modules]
        elif app.doc_type == RemoteApp._doc_type:
            return []

    def dehydrate(self, bundle):
        if not _safe_bool(bundle, "extras"):
            return super(ApplicationResource, self).dehydrate(bundle)
        else:
            app_data = {}
            app_data.update(bundle.obj._doc)
            app_data.update(bundle.data)
            return app_data

    def obj_get_list(self, bundle, domain, **kwargs):
        return get_apps_in_domain(domain, include_remote=False)

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Application, kwargs['pk'], kwargs['domain'])

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_apps)
        object_class = Application
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'application'


class HOPECaseResource(CommCareCaseResource):
    """
    Custom API endpoint for custom case wrapper
    """
    events_attributes = fields.ListField()
    other_properties = fields.DictField()

    def dehydrate_events_attributes(self, bundle):
        return bundle.obj.events_attributes

    def dehydrate_other_properties(self, bundle):
        return bundle.obj.other_properties

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

        # Note that CaseES is used only as an ES client, for `run_query` against the proper index
        return ElasticAPIQuerySet(
            payload=query,
            model=HOPECase,
            es_client=self.case_es(domain),
        ).order_by('server_modified_on')

    def alter_list_data_to_serialize(self, request, data):

        # rename 'properties' field to 'case_properties'
        for bundle in data['objects']:
            bundle.data['case_properties'] = bundle.data['properties']
            del bundle.data['properties']

        mother_lists = filter(lambda x: x.obj.type == CC_BIHAR_PREGNANCY, data['objects'])
        child_lists = filter(lambda x: x.obj.type == CC_BIHAR_NEWBORN, data['objects'])

        return {'objects': {
            'mother_lists': mother_lists,
            'child_lists': child_lists
        }, 'meta': data['meta']}

    class Meta(CommCareCaseResource.Meta):
        resource_name = 'hope-case'
