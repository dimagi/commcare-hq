from datetime import datetime
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from memoized import memoized

from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.exceptions import BadRequest

from casexml.apps.case.xform import get_case_updates
from corehq.apps.api.query_adapters import GroupQuerySetAdapter
from corehq.apps.api.resources.pagination import DoesNothingPaginatorCompat

from corehq.apps.api.es import ElasticAPIQuerySet, FormESView, es_query_from_get_params
from corehq.apps.api.fields import (
    ToManyDictField,
    ToManyDocumentsField,
    ToManyListDictField,
    UseIfRequested,
)
from corehq.apps.api.models import ESCase, ESXFormInstance
from corehq.apps.api.resources import (
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
    SimpleSortableResourceMixin,
    v0_1,
    v0_3,
)
from corehq.apps.api.resources.auth import (
    LoginAndDomainAuthentication,
    RequirePermissionAuthentication,
    SSOAuthentication,
)
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.resources.v0_1 import _safe_bool
from corehq.apps.api.serializers import (
    CommCareCaseSerializer,
    XFormInstanceSerializer,
)
from corehq.apps.api.util import get_obj, get_object_or_not_exist
from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties,
)
from corehq.apps.app_manager.dbaccessors import (
    get_all_built_app_results,
    get_apps_in_domain,
)
from corehq.apps.app_manager.models import Application, RemoteApp, LinkedApplication
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, HqPermissions
from corehq.apps.users.util import format_username
from corehq.motech.repeaters.models import CommCareCase
from corehq.util.view_utils import absolute_reverse
from no_exceptions.exceptions import Http400

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.
MOCK_XFORM_ES = None


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
    submit_ip = fields.CharField(attribute='submit_ip', blank=True, null=True)
    uiversion = fields.CharField(attribute='uiversion', blank=True, null=True)
    metadata = fields.DictField(attribute='metadata', blank=True, null=True)
    received_on = fields.CharField(attribute="received_on")
    edited_on = fields.CharField(attribute="edited_on", null=True)
    server_modified_on = fields.CharField(attribute="server_modified_on")
    indexed_on = fields.CharField(attribute='inserted_at')

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
            attribute=lambda xform: _cases_referenced_by_xform(xform)
        )
    )

    attachments = fields.DictField(readonly=True, null=True)

    def dehydrate_attachments(self, bundle):
        attachments_dict = getattr(bundle.obj, 'blobs', None)
        if not attachments_dict:
            return {}

        domain = bundle.obj.domain
        form_id = bundle.obj._id

        def _normalize_meta(name, meta):
            return {
                'content_type': meta.content_type,
                'length': meta.content_length,
                'url': absolute_reverse('api_form_attachment', args=(domain, form_id, name))
            }

        return {
            name: _normalize_meta(name, meta) for name, meta in attachments_dict.items()
        }

    is_phone_submission = fields.BooleanField(readonly=True)

    def dehydrate_is_phone_submission(self, bundle):
        headers = getattr(bundle.obj, 'openrosa_headers', None)
        if not headers:
            return False
        return headers.get('HTTP_X_OPENROSA_VERSION') is not None

    edited_by_user_id = fields.CharField(readonly=True, null=True)

    def dehydrate_edited_by_user_id(self, bundle):
        if bundle.obj.edited_on:
            return (getattr(bundle.obj, 'auth_context') or {}).get('user_id', None)

    def obj_get(self, bundle, **kwargs):
        instance_id = kwargs['pk']
        domain = kwargs['domain']
        return self.xform_es(domain).get_document(instance_id)

    def xform_es(self, domain):
        return MOCK_XFORM_ES or FormESView(domain)

    def obj_get_list(self, bundle, domain, **kwargs):
        try:
            es_query = es_query_from_get_params(bundle.request.GET, domain)
        except Http400 as e:
            raise BadRequest(str(e))

        # Note that FormESView is used only as an ES client, for `run_query` against the proper index
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
        authentication = RequirePermissionAuthentication(HqPermissions.edit_data)
        object_class = ESXFormInstance
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'form'
        ordering = ['received_on', 'server_modified_on', 'indexed_on']
        serializer = XFormInstanceSerializer(formats=['json'])


def _cases_referenced_by_xform(esxform):
    """Get a list of cases referenced by ESXFormInstance

    Note: this does not load cases referenced in stock transactions
    because ESXFormInstance does not have access to form XML, which
    is needed to find stock transactions.
    """
    assert esxform.domain, esxform.form_id
    case_ids = set(cu.id for cu in get_case_updates(esxform))
    return CommCareCase.objects.get_cases(list(case_ids), esxform.domain)


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

    date_modified = fields.CharField(attribute='modified_on', default="1900-01-01")
    indexed_on = fields.CharField(attribute='inserted_at', default="1900-01-01")
    server_date_modified = fields.CharField(attribute='server_modified_on', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_opened_on', default="1900-01-01")
    opened_by = fields.CharField(attribute='opened_by', null=True)
    closed_by = fields.CharField(attribute='closed_by', null=True)

    def obj_get(self, bundle, **kwargs):
        case_id = kwargs['pk']
        domain = kwargs['domain']
        return self.case_es(domain).get_document(case_id)

    class Meta(v0_3.CommCareCaseResource.Meta):
        max_limit = 5000
        serializer = CommCareCaseSerializer()
        ordering = ['server_date_modified', 'date_modified', 'indexed_on']
        object_class = ESCase


class GroupResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    id = fields.CharField(attribute='get_id', unique=True, readonly=True)
    domain = fields.CharField(attribute='domain')
    name = fields.CharField(attribute='name')

    users = fields.ListField(attribute='get_user_ids')

    case_sharing = fields.BooleanField(attribute='case_sharing', default=False)
    reporting = fields.BooleanField(default=True, attribute='reporting')

    metadata = fields.DictField(attribute='metadata', null=True, blank=True)

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Group, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        return GroupQuerySetAdapter(domain)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(HqPermissions.edit_commcare_users)
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
        authentication = SSOAuthentication()
        resource_name = 'sso'
        detail_allowed_methods = []
        list_allowed_methods = ['post']


class BaseApplicationResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):

    def obj_get_list(self, bundle, domain, **kwargs):
        return sorted(get_apps_in_domain(domain, include_remote=False),
                      key=lambda app: app.date_created or datetime.min)

    def obj_get(self, bundle, **kwargs):
        # support returning linked applications upon receiving an application request
        return get_object_or_not_exist(Application, kwargs['pk'], kwargs['domain'],
                                       additional_doc_types=[LinkedApplication._doc_type])

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication(allow_session_auth=True)
        object_class = Application
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'application'
        paginator_class = DoesNothingPaginatorCompat


class ApplicationResource(BaseApplicationResource):

    id = fields.CharField(attribute='_id')
    name = fields.CharField(attribute='name')
    version = fields.IntegerField(attribute='version')
    is_released = fields.BooleanField(attribute='is_released', null=True)
    built_on = fields.DateTimeField(attribute='built_on', null=True)
    build_comment = fields.CharField(attribute='build_comment', null=True)
    built_from_app_id = fields.CharField(attribute='copy_of', null=True)
    modules = fields.ListField()
    versions = fields.ListField()

    @staticmethod
    def dehydrate_versions(bundle):
        app = bundle.obj
        if app.copy_of:
            return []
        results = get_all_built_app_results(app.domain, app.get_id)
        return [
            {
                'id': result['value']['_id'],
                'built_on': result['value']['built_on'],
                'build_comment': result['value']['build_comment'],
                'is_released': result['value']['is_released'],
                'version': result['value']['version'],
            }
            for result in results
        ]

    @memoized
    def get_all_case_properties_local(self, app):
        return get_all_case_properties(app, exclude_invalid_properties=False)

    def dehydrate_module(self, app, module, langs):
        """
        Convert a Module object to a JValue representation
        with just the good parts.

        NOTE: This is not a tastypie "magic"-name method to
        dehydrate the "module" field; there is no such field.
        """
        try:
            dehydrated = {}

            dehydrated['name'] = module.name
            dehydrated['case_type'] = module.case_type

            all_case_properties = self.get_all_case_properties_local(app)
            dehydrated['case_properties'] = all_case_properties[module.case_type]

            dehydrated['unique_id'] = module.unique_id

            dehydrated['forms'] = []
            for form in module.get_forms():
                form_unique_id = form.unique_id
                form_jvalue = {
                    'xmlns': form.xmlns,
                    'name': form.name,
                    'questions': form.get_questions(
                        langs,
                        include_triggers=True,
                        include_groups=True,
                        include_translations=True,
                        include_fixtures=True,
                    ),
                    'unique_id': form_unique_id,
                }
                dehydrated['forms'].append(form_jvalue)
            return dehydrated
        except Exception as e:
            return {
                'error': str(e)
            }

    def dehydrate_modules(self, bundle):
        app = bundle.obj

        # support returning linked applications upon receiving an application list request
        if app.doc_type in [Application._doc_type, LinkedApplication._doc_type]:
            return [self.dehydrate_module(app, module, app.langs) for module in bundle.obj.get_modules()]
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
