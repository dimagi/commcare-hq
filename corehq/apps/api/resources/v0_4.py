from datetime import datetime
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from memoized import memoized

from tastypie import fields
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
from corehq.apps.api.util import (
    get_obj,
    get_object_or_not_exist,
    object_does_not_exist,
)
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


class XFormInstanceResource(SimpleSortableResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    """This version of the form resource is built of Elasticsearch data
    which gets wrapped by ``ESXFormInstance``.
    No type conversion is done e.g. dates and some fields are named differently than in the
    Python models.
    """

    id = fields.CharField(
        attribute='_id',
        readonly=True,
        unique=True,
        help_text='Form UUID.',
    )

    domain = fields.CharField(
        attribute='domain',
        help_text='Domain (project space) the form was submitted to.',
    )
    form = fields.DictField(
        attribute='form_data',
        help_text='The submitted form data, converted from XML to JSON, '
                  'keyed by question path.',
    )
    type = fields.CharField(
        attribute='type',
        help_text='Root data node type of the submitted form, typically '
                  '"data".',
    )
    version = fields.CharField(
        attribute='version',
        help_text='Version number of the form definition used for this '
                  'submission.',
    )
    submit_ip = fields.CharField(
        attribute='submit_ip',
        blank=True,
        null=True,
        help_text='IP address the form was submitted from.',
    )
    uiversion = fields.CharField(
        attribute='uiversion',
        blank=True,
        null=True,
        help_text='UI version of the form definition used for this '
                  'submission.',
    )
    metadata = fields.DictField(
        attribute='metadata',
        blank=True,
        null=True,
        help_text='Form metadata reported by the submitting device, '
                  'such as device ID, username, and start/end '
                  'timestamps.',
    )
    received_on = fields.CharField(
        attribute="received_on",
        help_text='Date and time the form was received by the server.',
    )
    edited_on = fields.CharField(
        attribute="edited_on",
        null=True,
        help_text='Date and time the form was last edited, or null if '
                  'it has not been edited.',
    )
    server_modified_on = fields.CharField(
        attribute="server_modified_on",
        help_text='Date and time the form was last modified on the '
                  'server.',
    )
    indexed_on = fields.CharField(
        attribute='inserted_at',
        help_text='Date and time the form was indexed into '
                  'Elasticsearch. Useful for pagination since it always '
                  'increases.',
    )

    app_id = fields.CharField(
        attribute='app_id',
        null=True,
        help_text='UUID of the application the form was submitted from.',
    )
    build_id = fields.CharField(
        attribute='build_id',
        null=True,
        help_text='UUID of the application build the form was '
                  'submitted from.',
    )
    initial_processing_complete = fields.BooleanField(
        attribute='initial_processing_complete',
        null=True,
        help_text='Whether initial processing of the form (such as '
                  'case updates) has completed.',
    )
    problem = fields.CharField(
        attribute='problem',
        null=True,
        help_text='Description of a processing error encountered for '
                  'this form, or null if there was none.',
    )

    archived = fields.CharField(
        readonly=True,
        help_text='Whether the form has been archived.',
    )

    def dehydrate_archived(self, bundle):
        return bundle.obj.is_archived

    cases = UseIfRequested(
        ToManyDocumentsField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute=lambda xform: _cases_referenced_by_xform(xform),
            help_text='Cases referenced by this form, not including '
                      'cases referenced only in stock transactions. '
                      'Returned only when cases__full=true is passed.',
        )
    )

    attachments = fields.DictField(
        readonly=True,
        null=True,
        help_text='Metadata for files attached to the form submission '
                  '(e.g. images, audio), keyed by attachment name, each '
                  'giving content_type, length and a download url.',
    )

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

    is_phone_submission = fields.BooleanField(
        readonly=True,
        help_text='Whether the form was submitted using the OpenRosa '
                  'protocol (e.g. from CommCare mobile), as opposed to '
                  'the web.',
    )

    def dehydrate_is_phone_submission(self, bundle):
        headers = getattr(bundle.obj, 'openrosa_headers', None)
        if not headers:
            return False
        return headers.get('HTTP_X_OPENROSA_VERSION') is not None

    edited_by_user_id = fields.CharField(
        readonly=True,
        null=True,
        help_text='UUID of the user who last edited the form, or null '
                  'if it has not been edited.',
    )

    def dehydrate_edited_by_user_id(self, bundle):
        if bundle.obj.edited_on:
            return (getattr(bundle.obj, 'auth_context') or {}).get('user_id', None)

    def obj_get(self, bundle, **kwargs):
        instance_id = kwargs['pk']
        domain = kwargs['domain']
        return self.xform_es(domain).get_document(instance_id)

    def xform_es(self, domain):
        return FormESView(domain)

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

    class Docs:
        summary = 'Forms'
        description = (
            'List form submissions in a project space, or fetch a '
            'single form by identifier. Forms are individual data '
            'submissions made from CommCare mobile or web apps.'
        )
        examples = {'list_response': 'form/v1/list_response.json'}
        field_schemas = {
            'cases': {
                'type': 'array',
                'items': {'type': 'object'},
            },
            'archived': {'type': 'boolean'},
            'resource_uri': {
                'description': 'URI of this record in the API.',
            },
        }
        parameters = [
            {
                'name': 'xmlns',
                'in': 'query',
                'required': False,
                'description': 'Form XML namespace.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'app_id',
                'in': 'query',
                'required': False,
                'description': 'Limit to forms submitted from this '
                              'application.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'received_on_start',
                'in': 'query',
                'required': False,
                'description': 'Only return forms received on or after '
                              'this date (and time).',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'received_on_end',
                'in': 'query',
                'required': False,
                'description': 'Only return forms received on or before '
                              'this date (and time).',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'indexed_on_start',
                'in': 'query',
                'required': False,
                'description': 'Only return forms indexed into '
                              'CommCare HQ on or after this date (and '
                              'time). Recommended for pagination, as it '
                              'handles edge cases better than '
                              'received_on.',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'indexed_on_end',
                'in': 'query',
                'required': False,
                'description': 'Only return forms indexed into '
                              'CommCare HQ on or before this date (and '
                              'time).',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'appVersion',
                'in': 'query',
                'required': False,
                'description': 'Exact version of the CommCare '
                              'application used to submit the form.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'include_archived',
                'in': 'query',
                'required': False,
                'description': 'When true, archived forms are included '
                              'in the response.',
                'schema': {'type': 'boolean'},
            },
            {
                'name': 'case_id',
                'in': 'query',
                'required': False,
                'description': 'Only return forms that updated the '
                              'case with this UUID.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'cases__full',
                'in': 'query',
                'required': False,
                'description': 'When true, include the full case '
                              'objects referenced by this form in the '
                              '"cases" field.',
                'schema': {'type': 'boolean'},
            },
        ]

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
    return CommCareCase.objects.get_cases(list(case_ids))


class CommCareCaseResource(SimpleSortableResourceMixin, v0_3.CommCareCaseResource, DomainSpecificResourceMixin):
    xforms_by_name = UseIfRequested(ToManyListDictField(
        'corehq.apps.api.resources.v0_4.XFormInstanceResource',
        attribute='xforms_by_name',
        help_text='Forms that have updated this case, grouped by form '
                  'name. Returned only when xforms_by_name__full=true '
                  'is passed.',
    ))

    xforms_by_xmlns = UseIfRequested(ToManyListDictField(
        'corehq.apps.api.resources.v0_4.XFormInstanceResource',
        attribute='xforms_by_xmlns',
        help_text='Forms that have updated this case, grouped by form '
                  'XMLNS. Returned only when xforms_by_xmlns__full=true '
                  'is passed.',
    ))

    child_cases = UseIfRequested(
        ToManyDictField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute='child_cases',
            help_text='Child cases of this case, keyed by index '
                      'identifier. Returned only when '
                      'child_cases__full=true is passed.',
        )
    )

    parent_cases = UseIfRequested(
        ToManyDictField(
            'corehq.apps.api.resources.v0_4.CommCareCaseResource',
            attribute='parent_cases',
            help_text='Parent cases of this case, keyed by index '
                      'identifier. Returned only when '
                      'parent_cases__full=true is passed.',
        )
    )

    domain = fields.CharField(
        attribute='domain',
        help_text='Domain (project space) that owns the case.',
    )

    date_modified = fields.CharField(
        attribute='modified_on',
        default="1900-01-01",
        help_text='Date and time the case was last modified, as '
                  'reported by the submitting phone.',
    )
    indexed_on = fields.CharField(
        attribute='inserted_at',
        default="1900-01-01",
        help_text='Date and time the case was indexed into '
                  'Elasticsearch. Useful for pagination since it '
                  'always increases, unlike phone-reported dates.',
    )
    server_date_modified = fields.CharField(
        attribute='server_modified_on',
        default="1900-01-01",
        help_text='Date and time the case was last modified on the '
                  'server.',
    )
    server_date_opened = fields.CharField(
        attribute='server_opened_on',
        default="1900-01-01",
        help_text='Date and time the case was opened on the server.',
    )
    opened_by = fields.CharField(
        attribute='opened_by',
        null=True,
        help_text='UUID of the user who opened the case.',
    )
    closed_by = fields.CharField(
        attribute='closed_by',
        null=True,
        help_text='UUID of the user who closed the case, or null if '
                  'the case is open.',
    )

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        case_id = kwargs['pk']
        if not case_id:
            raise object_does_not_exist('CommCareCase', '')
        return self.case_es(domain).get_document(case_id)

    class Docs:
        summary = 'Cases'
        description = (
            'List cases in a project space, or fetch a single case by '
            'identifier. Cases track structured data about a person, '
            'place or thing, collected and updated by CommCare mobile '
            'or web app forms.'
        )
        examples = {'list_response': 'case/v1/list_response.json'}
        field_schemas = {
            'xform_ids': {
                'items': {'type': 'string'},
            },
            'xforms_by_name': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'array',
                    'items': {'type': 'object'},
                },
            },
            'xforms_by_xmlns': {
                'type': 'object',
                'additionalProperties': {
                    'type': 'array',
                    'items': {'type': 'object'},
                },
            },
            'child_cases': {
                'type': 'object',
                'additionalProperties': {'type': 'object'},
            },
            'parent_cases': {
                'type': 'object',
                'additionalProperties': {'type': 'object'},
            },
            'resource_uri': {
                'description': 'URI of this record in the API.',
            },
        }
        parameters = [
            {
                'name': 'owner_id',
                'in': 'query',
                'required': False,
                'description': 'User or group UUID. Returns all cases '
                              'owned by that entity (should not be '
                              'used together with user_id).',
                'schema': {'type': 'string'},
            },
            {
                'name': 'user_id',
                'in': 'query',
                'required': False,
                'description': 'User UUID. Returns all cases last '
                              'modified by that user.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'type',
                'in': 'query',
                'required': False,
                'description': 'Return only cases matching this case '
                              'type.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'closed',
                'in': 'query',
                'required': False,
                'description': 'Filter by case status: true for closed '
                              'cases, false for open cases. Omit to '
                              'return both.',
                'schema': {'type': 'boolean'},
            },
            {
                'name': 'indexed_on_start',
                'in': 'query',
                'required': False,
                'description': 'Only return cases that have had data '
                              'modified on or after this date (and '
                              'time). Recommended for pagination, as it '
                              'handles edge cases better than '
                              'server_date_modified.',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'indexed_on_end',
                'in': 'query',
                'required': False,
                'description': 'Only return cases that have had data '
                              'modified on or before this date (and '
                              'time).',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'date_modified_start',
                'in': 'query',
                'required': False,
                'description': 'Only return cases modified on or after '
                              'this date (phone-reported date). '
                              'Defaults to the first submission date.',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'date_modified_end',
                'in': 'query',
                'required': False,
                'description': 'Only return cases modified on or before '
                              'this date (phone-reported date). '
                              'Defaults to the current date.',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'server_date_modified_start',
                'in': 'query',
                'required': False,
                'description': 'Only return cases modified on or after '
                              'this date (server date). Defaults to '
                              'the first submission date.',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'server_date_modified_end',
                'in': 'query',
                'required': False,
                'description': 'Only return cases modified on or '
                              'before this date (server date). '
                              'Defaults to the current date.',
                'schema': {'type': 'string', 'format': 'date-time'},
            },
            {
                'name': 'name',
                'in': 'query',
                'required': False,
                'description': 'Filter cases by case name.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'external_id',
                'in': 'query',
                'required': False,
                'description': "Filter cases by the case's external_id "
                              'property.',
                'schema': {'type': 'string'},
            },
            {
                'name': 'child_cases__full',
                'in': 'query',
                'required': False,
                'description': 'When true, include the full child '
                              'case objects in the "child_cases" field.',
                'schema': {'type': 'boolean'},
            },
            {
                'name': 'parent_cases__full',
                'in': 'query',
                'required': False,
                'description': 'When true, include the full parent '
                              'case objects in the "parent_cases" '
                              'field.',
                'schema': {'type': 'boolean'},
            },
            {
                'name': 'xforms_by_name__full',
                'in': 'query',
                'required': False,
                'description': 'When true, include the full form '
                              'objects in the "xforms_by_name" field.',
                'schema': {'type': 'boolean'},
            },
            {
                'name': 'xforms_by_xmlns__full',
                'in': 'query',
                'required': False,
                'description': 'When true, include the full form '
                              'objects in the "xforms_by_xmlns" field.',
                'schema': {'type': 'boolean'},
            },
        ]

    class Meta(v0_3.CommCareCaseResource.Meta):
        max_limit = 5000
        serializer = CommCareCaseSerializer()
        ordering = ['server_date_modified', 'date_modified', 'indexed_on']
        object_class = ESCase


class GroupResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    id = fields.CharField(
        attribute='get_id',
        unique=True,
        readonly=True,
        help_text='Group UUID.',
    )
    domain = fields.CharField(
        attribute='domain',
        help_text='Domain (project space) that owns the group.',
    )
    name = fields.CharField(
        attribute='name',
        help_text='Name of the group.',
    )

    users = fields.ListField(
        attribute='get_user_ids',
        help_text='UUIDs of the users in this group.',
    )

    case_sharing = fields.BooleanField(
        attribute='case_sharing',
        default=False,
        help_text='Whether members of this group share cases with '
                  'each other.',
    )
    reporting = fields.BooleanField(
        default=True,
        attribute='reporting',
        help_text='Whether this group appears in the group filter '
                  'list for reports.',
    )

    metadata = fields.DictField(
        attribute='metadata',
        null=True,
        blank=True,
        help_text='Custom metadata associated with the group.',
    )

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Group, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, bundle, domain, **kwargs):
        return GroupQuerySetAdapter(domain)

    class Docs:
        summary = 'Groups'
        description = (
            'List the groups in a project space, or fetch a single '
            'group by identifier. Groups collect mobile workers for '
            'case sharing and reporting.'
        )
        examples = {'list_response': 'group/v1/list_response.json'}
        field_schemas = {
            'users': {
                'items': {'type': 'string'},
            },
            'resource_uri': {
                'description': 'URI of this record in the API.',
            },
        }

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

    class Docs:
        list_write_responses = {
            # post_list() is a complete override, not the generic
            # create/return-data path: it returns 200 (not 201) with the
            # authenticated user's full record, dehydrated by whichever
            # of CommCareUserResource/WebUserResource matches -- there
            # is no single fixed shape to publish, so the body is left
            # undeclared rather than picking one arbitrarily.
            'post': {
                '200': {
                    'description': 'The authenticated user, serialized '
                                  'as a mobile worker or web user '
                                  'record depending on the account '
                                  'type.',
                },
            },
        }

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
