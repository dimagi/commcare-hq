from __future__ import absolute_import
from __future__ import unicode_literals
from django.http import HttpResponseForbidden, HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from tastypie import fields
from tastypie.authentication import Authentication
from tastypie.bundle import Bundle
from tastypie.exceptions import BadRequest

from casexml.apps.case.xform import get_case_updates
from corehq.apps.api.es import XFormES, ElasticAPIQuerySet, es_search
from corehq.apps.api.fields import ToManyDocumentsField, UseIfRequested, ToManyDictField, ToManyListDictField
from corehq.apps.api.models import ESXFormInstance, ESCase
from corehq.apps.api.resources import (
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
    SimpleSortableResourceMixin,
    v0_1,
    v0_3,
)
from corehq.apps.api.resources.auth import DomainAdminAuthentication, RequirePermissionAuthentication, \
    LoginAndDomainAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.resources.v0_1 import _safe_bool
from corehq.apps.api.serializers import CommCareCaseSerializer, XFormInstanceSerializer
from corehq.apps.api.util import get_object_or_not_exist, get_obj
from corehq.apps.app_manager.app_schemas.case_properties import get_case_properties
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain, get_all_built_app_results
from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, Permissions
from corehq.apps.users.util import format_username
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeaters.models import Repeater
from corehq.motech.repeaters.utils import get_all_repeater_types
from corehq.util.view_utils import absolute_reverse
from couchforms.models import doc_types
from custom.hope.models import HOPECase, CC_BIHAR_NEWBORN, CC_BIHAR_PREGNANCY
from no_exceptions.exceptions import Http400
import six

# By the time a test case is running, the resource is already instantiated,
# so as a hack until this can be remedied, there is a global that
# can be set to provide a mock.
MOCK_XFORM_ES = None

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
        return MOCK_XFORM_ES or XFormES(domain)

    def obj_get_list(self, bundle, domain, **kwargs):
        include_archived = 'include_archived' in bundle.request.GET
        try:
            es_query = es_search(bundle.request, domain, ['include_archived'])
        except Http400 as e:
            raise BadRequest(six.text_type(e))
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
        ordering = ['received_on', 'server_modified_on']
        serializer = XFormInstanceSerializer(formats=['json'])


def _cases_referenced_by_xform(esxform):
    """Get a list of cases referenced by ESXFormInstance

    Note: this does not load cases referenced in stock transactions
    because ESXFormInstance does not have access to form XML, which
    is needed to find stock transactions.
    """
    assert esxform.domain, esxform.form_id
    case_ids = set(cu.id for cu in get_case_updates(esxform))
    return CaseAccessors(esxform.domain).get_cases(list(case_ids))


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
                                       additional_doc_types=list(get_all_repeater_types()))

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

    date_modified = fields.CharField(attribute='modified_on', default="1900-01-01")
    indexed_on = fields.CharField(attribute='inserted_at', default="1900-01-01")
    server_date_modified = fields.CharField(attribute='server_modified_on', default="1900-01-01")
    server_date_opened = fields.CharField(attribute='server_opened_on', default="1900-01-01")
    opened_by = fields.CharField(attribute='opened_by', null=True)

    def obj_get(self, bundle, **kwargs):
        case_id = kwargs['pk']
        domain = kwargs['domain']
        return self.case_es(domain).get_document(case_id)

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


class BaseApplicationResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):

    def obj_get_list(self, bundle, domain, **kwargs):
        return get_apps_in_domain(domain, include_remote=False)

    def obj_get(self, bundle, **kwargs):
        return get_object_or_not_exist(Application, kwargs['pk'], kwargs['domain'])

    class Meta(CustomResourceMeta):
        authentication = LoginAndDomainAuthentication()
        object_class = Application
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'application'


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

    @staticmethod
    def dehydrate_module(app, module, langs):
        """
        Convert a Module object to a JValue representation
        with just the good parts.

        NOTE: This is not a tastypie "magic"-name method to
        dehydrate the "module" field; there is no such field.
        """
        try:
            dehydrated = {}

            dehydrated['case_type'] = module.case_type

            dehydrated['case_properties'] = get_case_properties(
                app, [module.case_type], defaults=['name']
            )[module.case_type]

            dehydrated['unique_id'] = module.unique_id

            dehydrated['forms'] = []
            for form in module.forms:
                form_unique_id = form.unique_id
                form_jvalue = {
                    'xmlns': form.xmlns,
                    'name': form.name,
                    'questions': form.get_questions(
                        langs,
                        include_triggers=True,
                        include_groups=True,
                        include_translations=True),
                    'unique_id': form_unique_id,
                }
                dehydrated['forms'].append(form_jvalue)
            return dehydrated
        except Exception as e:
            return {
                'error': six.text_type(e)
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
        queryset = super(HOPECaseResource, self).obj_get_list(bundle, domain, **kwargs)
        queryset.model = HOPECase
        return queryset

    def alter_list_data_to_serialize(self, request, data):

        # rename 'properties' field to 'case_properties'
        for bundle in data['objects']:
            bundle.data['case_properties'] = bundle.data['properties']
            del bundle.data['properties']

        mother_lists = [x for x in data['objects'] if x.obj.type == CC_BIHAR_PREGNANCY]
        child_lists = [x for x in data['objects'] if x.obj.type == CC_BIHAR_NEWBORN]

        return {'objects': {
            'mother_lists': mother_lists,
            'child_lists': child_lists
        }, 'meta': data['meta']}

    class Meta(CommCareCaseResource.Meta):
        resource_name = 'hope-case'
