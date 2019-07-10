from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple
from itertools import chain

import six
from django.conf.urls import url
from django.contrib.auth.models import User
from django.forms import ValidationError
from django.http import Http404, HttpResponse, HttpResponseNotFound
from django.urls import reverse
from six.moves import map
from tastypie import fields
from tastypie import http
from tastypie.authentication import ApiKeyAuthentication
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.bundle import Bundle
from tastypie.exceptions import BadRequest, ImmediateHttpResponse, NotFound
from tastypie.http import HttpForbidden, HttpUnauthorized
from tastypie.resources import convert_post_to_patch, ModelResource, Resource
from tastypie.utils import dict_strip_unicode_keys

from casexml.apps.stock.models import StockTransaction
from corehq import privileges, toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.api.odata.serializers import (
    ODataCaseSerializer,
    ODataFormSerializer,
    DeprecatedODataCaseSerializer,
    DeprecatedODataFormSerializer,
)
from corehq.apps.api.odata.utils import record_feed_access_in_datadog
from corehq.apps.api.odata.views import add_odata_headers
from corehq.apps.api.resources.auth import RequirePermissionAuthentication, AdminAuthentication, \
    ODataAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import get_obj
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.es import UserES
from corehq.apps.export.esaccessors import get_case_export_base_query, get_form_export_base_query
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.groups.models import Group
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.apps.sms.util import strip_plus
from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn
from corehq.apps.userreports.models import ReportConfiguration, \
    StaticReportConfiguration, report_config_id_is_static
from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
from corehq.apps.userreports.reports.view import query_dict_to_dict, \
    get_filter_values
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_id_username_pairs_by_domain
from corehq.apps.users.models import CommCareUser, WebUser, Permissions, CouchUser, UserRole
from corehq.apps.users.util import raw_username
from corehq.util import get_document_or_404
from corehq.util.couch import get_document_or_not_found, DocumentNotFound
from corehq.util.timer import TimingContext
from phonelog.models import DeviceReportEntry
from . import HqBaseResource, DomainSpecificResourceMixin
from . import v0_1, v0_4, CouchResourceMixin
from .pagination import NoCountingPaginator, DoesNothingPaginator

MOCK_BULK_USER_ES = None


def user_es_call(domain, q, fields, size, start_at):
    query = (UserES()
             .domain(domain)
             .fields(fields)
             .size(size)
             .start(start_at))
    if q is not None:
        query.set_query({"query_string": {"query": q}})
    return query.run().hits


def _set_role_for_bundle(kwargs, bundle):
    # check for roles associated with the domain
    domain_roles = UserRole.by_domain_and_name(kwargs['domain'], bundle.data.get('role'))
    if domain_roles:
        qualified_role_id = domain_roles[0].get_qualified_id()
        bundle.obj.set_role(kwargs['domain'], qualified_role_id)
    else:
        # check for preset roles and now create them for the domain
        permission_preset_name = UserRole.get_preset_permission_by_name(bundle.data.get('role'))
        if permission_preset_name:
            bundle.obj.set_role(kwargs['domain'], permission_preset_name)

class BulkUserResource(HqBaseResource, DomainSpecificResourceMixin):
    """
    A read-only user data resource based on elasticsearch.
    Supported Params: limit offset q fields
    """
    type = "bulk-user"
    id = fields.CharField(attribute='id', readonly=True, unique=True)
    email = fields.CharField(attribute='email')
    username = fields.CharField(attribute='username', unique=True)
    first_name = fields.CharField(attribute='first_name', null=True)
    last_name = fields.CharField(attribute='last_name', null=True)
    phone_numbers = fields.ListField(attribute='phone_numbers', null=True)

    @staticmethod
    def to_obj(user):
        '''
        Takes a flat dict and returns an object
        '''
        if '_id' in user:
            user['id'] = user.pop('_id')
        return namedtuple('user', list(user))(**user)

    class Meta(CustomResourceMeta):
        authentication = RequirePermissionAuthentication(Permissions.edit_commcare_users)
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        object_class = object
        resource_name = 'bulk-user'

    def dehydrate(self, bundle):
        fields = bundle.request.GET.getlist('fields')
        data = {}
        if not fields:
            return bundle
        for field in fields:
            data[field] = bundle.data[field]
        bundle.data = data
        return bundle

    def obj_get_list(self, bundle, **kwargs):
        request_fields = bundle.request.GET.getlist('fields')
        for field in request_fields:
            if field not in self.fields:
                raise BadRequest('{0} is not a valid field'.format(field))

        params = bundle.request.GET
        param = lambda p: params.get(p, None)
        fields = list(self.fields)
        fields.remove('id')
        fields.append('_id')
        fn = MOCK_BULK_USER_ES or user_es_call
        users = fn(
            domain=kwargs['domain'],
            q=param('q'),
            fields=fields,
            size=param('limit'),
            start_at=param('offset'),
        )
        return list(map(self.to_obj, users))

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'pk': get_obj(bundle_or_obj).id
        }


class CommCareUserResource(v0_1.CommCareUserResource):

    class Meta(v0_1.CommCareUserResource.Meta):
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']
        always_return_data = True

    def serialize(self, request, data, format, options=None):
        if not isinstance(data, dict) and request.method == 'POST':
            data = {'id': data.obj._id}
        return self._meta.serializer.serialize(data, format, options)

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if bundle_or_obj is None:
            return super(CommCareUserResource, self).get_resource_uri(bundle_or_obj, url_name)
        elif isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        else:
            obj = bundle_or_obj

        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=obj.domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def _update(self, bundle):
        should_save = False
        for key, value in bundle.data.items():
            if getattr(bundle.obj, key, None) != value:
                if key == 'phone_numbers':
                    bundle.obj.phone_numbers = []
                    for idx, phone_number in enumerate(bundle.data.get('phone_numbers', [])):

                        bundle.obj.add_phone_number(strip_plus(phone_number))
                        if idx == 0:
                            bundle.obj.set_default_phone_number(strip_plus(phone_number))
                        should_save = True
                elif key == 'groups':
                    bundle.obj.set_groups(bundle.data.get("groups", []))
                    should_save = True
                elif key in ['email', 'username']:
                    setattr(bundle.obj, key, value.lower())
                    should_save = True
                elif key == 'password':
                    domain = Domain.get_by_name(bundle.obj.domain)
                    if domain.strong_mobile_passwords:
                        try:
                            clean_password(bundle.data.get("password"))
                        except ValidationError as e:
                            if not hasattr(bundle.obj, 'errors'):
                                bundle.obj.errors = []
                            bundle.obj.errors.append(six.text_type(e))
                            return False
                    bundle.obj.set_password(bundle.data.get("password"))
                    should_save = True
                else:
                    setattr(bundle.obj, key, value)
                    should_save = True
        return should_save

    def obj_create(self, bundle, request=None, **kwargs):
        try:
            bundle.obj = CommCareUser.create(
                domain=kwargs['domain'],
                username=bundle.data['username'].lower(),
                password=bundle.data['password'],
                email=bundle.data.get('email', '').lower(),
            )
            del bundle.data['password']
            self._update(bundle)
            bundle.obj.save()
        except Exception:
            if bundle.obj._id:
                bundle.obj.retire()
            try:
                django_user = bundle.obj.get_django_user()
            except User.DoesNotExist:
                pass
            else:
                django_user.delete()
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = CommCareUser.get(kwargs['pk'])
        assert bundle.obj.domain == kwargs['domain']
        if self._update(bundle):
            assert bundle.obj.domain == kwargs['domain']
            bundle.obj.save()
            return bundle
        else:
            raise BadRequest(''.join(chain.from_iterable(bundle.obj.errors)))

    def obj_delete(self, bundle, **kwargs):
        user = CommCareUser.get(kwargs['pk'])
        if user:
            user.retire()
        return ImmediateHttpResponse(response=http.HttpAccepted())

class WebUserResource(v0_1.WebUserResource):

    class Meta(v0_1.WebUserResource.Meta):
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post']
        always_return_data = True

    def serialize(self, request, data, format, options=None):
        if not isinstance(data, dict) and request.method == 'POST':
            data = {'id': data.obj._id}
        return self._meta.serializer.serialize(data, format, options)

    def dispatch(self, request_type, request, **kwargs):
        """
        Override dispatch to check for proper params for user create : role and admin permissions
        """
        if request.method == 'POST':
            details = self._meta.serializer.deserialize(request.body)
            if details.get('is_admin', False):
                if self._admin_assigned_another_role(details):
                    raise BadRequest("An admin can have only one role : Admin")
            else:
                if not details.get('role', None):
                    raise BadRequest("Please assign role for non admin user")
                elif self._invalid_user_role(request, details):
                    raise BadRequest("Invalid User Role %s" % details.get('role', None))

        return super(WebUserResource, self).dispatch(request_type, request, **kwargs)

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if isinstance(bundle_or_obj, Bundle):
            domain = bundle_or_obj.request.domain
            obj = bundle_or_obj.obj
        elif bundle_or_obj is None:
            return None

        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def _update(self, bundle):
        should_save = False
        for key, value in bundle.data.items():
            if getattr(bundle.obj, key, None) != value:
                if key == 'phone_numbers':
                    bundle.obj.phone_numbers = []
                    for idx, phone_number in enumerate(bundle.data.get('phone_numbers', [])):
                        bundle.obj.add_phone_number(strip_plus(phone_number))
                        if idx == 0:
                            bundle.obj.set_default_phone_number(strip_plus(phone_number))
                        should_save = True
                elif key in ['email', 'username']:
                    setattr(bundle.obj, key, value.lower())
                    should_save = True
                else:
                    setattr(bundle.obj, key, value)
                    should_save = True
        return should_save

    def obj_create(self, bundle, request=None, **kwargs):
        try:
            self._meta.domain = kwargs['domain']
            bundle.obj = WebUser.create(
                domain=kwargs['domain'],
                username=bundle.data['username'].lower(),
                password=bundle.data['password'],
                email=bundle.data.get('email', '').lower(),
                is_admin=bundle.data.get('is_admin', False)
            )
            del bundle.data['password']
            self._update(bundle)
            # is_admin takes priority over role
            if not bundle.obj.is_admin and bundle.data.get('role'):
                _set_role_for_bundle(kwargs, bundle)
            bundle.obj.save()
        except Exception:
            bundle.obj.delete()
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = WebUser.get(kwargs['pk'])
        assert kwargs['domain'] in bundle.obj.domains
        if self._update(bundle):
            assert kwargs['domain'] in bundle.obj.domains
            bundle.obj.save()
        return bundle

    def _invalid_user_role(self, request, details):
        return details.get('role') not in UserRole.preset_and_domain_role_names(request.domain)

    def _admin_assigned_another_role(self, details):
        # default value Admin since that will be assigned later anyway since is_admin is True
        return details.get('role', 'Admin') != 'Admin'

class AdminWebUserResource(v0_1.UserResource):
    domains = fields.ListField(attribute='domains')

    def obj_get(self, bundle, **kwargs):
        return WebUser.get(kwargs['pk'])

    def obj_get_list(self, bundle, **kwargs):
        if 'username' in bundle.request.GET:
            return [WebUser.get_by_username(bundle.request.GET['username'])]
        return [WebUser.wrap(u) for u in UserES().web_users().run().hits]

    class Meta(WebUserResource.Meta):
        authentication = AdminAuthentication()
        detail_allowed_methods = ['get']
        list_allowed_methods = ['get']


class GroupResource(v0_4.GroupResource):

    class Meta(v0_4.GroupResource.Meta):
        detail_allowed_methods = ['get', 'put', 'delete']
        list_allowed_methods = ['get', 'post', 'patch']
        always_return_data = True

    def serialize(self, request, data, format, options=None):
        if not isinstance(data, dict):
            if 'error_message' in data.data:
                data = {'error_message': data.data['error_message']}
            elif request.method == 'POST':
                data = {'id': data.obj._id}
        return self._meta.serializer.serialize(data, format, options)

    def patch_list(self, request=None, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.14/tastypie/resources.py#L1466
        (BSD licensed) and modified to pass the kwargs to `obj_create` and support only create method
        """
        request = convert_post_to_patch(request)
        deserialized = self.deserialize(request, request.body, format=request.META.get('CONTENT_TYPE', 'application/json'))

        collection_name = self._meta.collection_name
        if collection_name not in deserialized:
            raise BadRequest("Invalid data sent: missing '%s'" % collection_name)

        if len(deserialized[collection_name]) and 'put' not in self._meta.detail_allowed_methods:
            raise ImmediateHttpResponse(response=http.HttpMethodNotAllowed())

        bundles_seen = []
        status = http.HttpAccepted
        for data in deserialized[collection_name]:

            data = self.alter_deserialized_detail_data(request, data)
            bundle = self.build_bundle(data=dict_strip_unicode_keys(data), request=request)
            try:

                self.obj_create(bundle=bundle, **self.remove_api_resource_names(kwargs))
            except AssertionError as e:
                status = http.HttpBadRequest
                bundle.data['_id'] = six.text_type(e)
            bundles_seen.append(bundle)

        to_be_serialized = [bundle.data['_id'] for bundle in bundles_seen]
        return self.create_response(request, to_be_serialized, response_class=status)

    def post_list(self, request, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.14/tastypie/resources.py#L1314
        (BSD licensed) and modified to catch Exception and not returning traceback
        """
        deserialized = self.deserialize(request, request.body, format=request.META.get('CONTENT_TYPE', 'application/json'))
        deserialized = self.alter_deserialized_detail_data(request, deserialized)
        bundle = self.build_bundle(data=dict_strip_unicode_keys(deserialized), request=request)
        try:
            updated_bundle = self.obj_create(bundle, **self.remove_api_resource_names(kwargs))
            location = self.get_resource_uri(updated_bundle)

            if not self._meta.always_return_data:
                return http.HttpCreated(location=location)
            else:
                updated_bundle = self.full_dehydrate(updated_bundle)
                updated_bundle = self.alter_detail_data_to_serialize(request, updated_bundle)
                return self.create_response(request, updated_bundle, response_class=http.HttpCreated, location=location)
        except AssertionError as e:
            bundle.data['error_message'] = six.text_type(e)
            return self.create_response(request, bundle, response_class=http.HttpBadRequest)

    def _update(self, bundle):
        should_save = False
        for key, value in bundle.data.items():
            if key == 'name' and getattr(bundle.obj, key, None) != value:
                if not Group.by_name(bundle.obj.domain, value):
                    setattr(bundle.obj, key, value or '')
                    should_save = True
                else:
                    raise Exception("A group with this name already exists")
            if key == 'users' and getattr(bundle.obj, key, None) != value:
                users_to_add = set(value) - set(bundle.obj.users)
                users_to_remove = set(bundle.obj.users) - set(value)
                for user in users_to_add:
                    bundle.obj.add_user(user)
                    should_save = True
                for user in users_to_remove:
                    bundle.obj.remove_user(user)
                    should_save = True
            elif getattr(bundle.obj, key, None) != value:
                setattr(bundle.obj, key, value)
                should_save = True
        return should_save

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if bundle_or_obj is None:
            return super(GroupResource, self).get_resource_uri(bundle_or_obj, url_name)
        elif isinstance(bundle_or_obj, Bundle):
            obj = bundle_or_obj.obj
        else:
            obj = bundle_or_obj
        return reverse('api_dispatch_detail', kwargs=dict(resource_name=self._meta.resource_name,
                                                          domain=obj.domain,
                                                          api_name=self._meta.api_name,
                                                          pk=obj._id))

    def obj_create(self, bundle, request=None, **kwargs):
        if not Group.by_name(kwargs['domain'], bundle.data.get("name")):
            bundle.obj = Group(bundle.data)
            bundle.obj.name = bundle.obj.name or ''
            bundle.obj.domain = kwargs['domain']
            bundle.obj.save()
            for user in bundle.obj.users:
                CommCareUser.get(user).set_groups([bundle.obj._id])
        else:
            raise AssertionError("A group with name %s already exists" % bundle.data.get("name"))
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = Group.get(kwargs['pk'])
        assert bundle.obj.domain == kwargs['domain']
        if self._update(bundle):
            assert bundle.obj.domain == kwargs['domain']
            bundle.obj.save()
        return bundle

    def obj_delete(self, bundle, **kwargs):
        group = self.obj_get(bundle, **kwargs)
        group.soft_delete()
        return bundle

class DomainAuthorization(ReadOnlyAuthorization):

    def __init__(self, domain_key='domain', *args, **kwargs):
        self.domain_key = domain_key

    def read_list(self, object_list, bundle):
        return object_list.filter(**{self.domain_key: bundle.request.domain})


class DeviceReportResource(HqBaseResource, ModelResource):

    class Meta(object):
        queryset = DeviceReportEntry.objects.all()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'device-log'
        authentication = RequirePermissionAuthentication(Permissions.edit_data)
        authorization = DomainAuthorization()
        paginator_class = NoCountingPaginator
        filtering = {
            # this is needed for the domain filtering but any values passed in via the URL get overridden
            "domain": ('exact',),
            "date": ('exact', 'gt', 'gte', 'lt', 'lte', 'range'),
            "user_id": ('exact',),
            "username": ('exact',),
            "type": ('exact',),
            "xform_id": ('exact',),
            "device_id": ('exact',),
        }


class StockTransactionResource(HqBaseResource, ModelResource):

    class Meta(object):
        queryset = StockTransaction.objects.all()
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get']
        resource_name = 'stock_transaction'
        authentication = RequirePermissionAuthentication(Permissions.view_reports)
        paginator_class = NoCountingPaginator
        authorization = DomainAuthorization(domain_key='report__domain')

        filtering = {
            "case_id": ('exact',),
            "section_id": ('exact'),
        }

        fields = ['case_id', 'product_id', 'type', 'section_id', 'quantity', 'stock_on_hand']
        include_resource_uri = False

    def build_filters(self, filters=None):
        orm_filters = super(StockTransactionResource, self).build_filters(filters)
        if 'start_date' in filters:
            orm_filters['report__date__gte'] = filters['start_date']
        if 'end_date' in filters:
            orm_filters['report__date__lte'] = filters['end_date']
        return orm_filters

    def dehydrate(self, bundle):
        bundle.data['product_name'] = bundle.obj.sql_product.name
        bundle.data['transaction_date'] = bundle.obj.report.date
        return bundle


ConfigurableReportData = namedtuple("ConfigurableReportData", [
    "data", "columns", "id", "domain", "total_records", "get_params", "next_page"
])


class ConfigurableReportDataResource(HqBaseResource, DomainSpecificResourceMixin):
    """
    A resource that replicates the behavior of the ajax part of the
    ConfigurableReportView view.
    """
    data = fields.ListField(attribute="data", readonly=True)
    columns = fields.ListField(attribute="columns", readonly=True)
    total_records = fields.IntegerField(attribute="total_records", readonly=True)
    next_page = fields.CharField(attribute="next_page", readonly=True)

    LIMIT_DEFAULT = 50
    LIMIT_MAX = 50

    def _get_start_param(self, bundle):
        try:
            start = int(bundle.request.GET.get('offset', 0))
            if start < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise BadRequest("start must be a positive integer.")
        return start

    def _get_limit_param(self, bundle):
        try:
            limit = int(bundle.request.GET.get('limit', self.LIMIT_DEFAULT))
            if limit < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise BadRequest("limit must be a positive integer.")

        if limit > self.LIMIT_MAX:
            raise BadRequest("Limit may not exceed {}.".format(self.LIMIT_MAX))
        return limit

    def _get_next_page(self, domain, id_, start, limit, total_records, get_query_dict):
        if total_records > start + limit:
            start += limit
            new_get_params = get_query_dict.copy()
            new_get_params["offset"] = start
            # limit has not changed, but it may not have been present in get params before.
            new_get_params["limit"] = limit
            return reverse('api_dispatch_detail', kwargs=dict(
                api_name=self._meta.api_name,
                resource_name=self._meta.resource_name,
                domain=domain,
                pk=id_,
            )) + "?" + new_get_params.urlencode()
        else:
            return ""

    def _get_report_data(self, report_config, domain, start, limit, get_params):
        report = ConfigurableReportDataSource.from_spec(report_config)

        string_type_params = [
            filter.name
            for filter in report_config.ui_filters
            if getattr(filter, 'datatype', 'string') == "string"
        ]
        filter_values = get_filter_values(
            report_config.ui_filters,
            query_dict_to_dict(get_params, domain, string_type_params)
        )
        report.set_filter_values(filter_values)

        page = list(report.get_data(start=start, limit=limit))

        columns = []
        for column in report.columns:
            simple_column = {
                "header": column.header,
                "slug": column.slug,
            }
            if isinstance(column, UCRExpandDatabaseSubcolumn):
                simple_column['expand_column_value'] = column.expand_value
            columns.append(simple_column)

        total_records = report.get_total_records()
        return page, columns, total_records

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        start = self._get_start_param(bundle)
        limit = self._get_limit_param(bundle)

        report_config = self._get_report_configuration(pk, domain)
        page, columns, total_records = self._get_report_data(
            report_config, domain, start, limit, bundle.request.GET)

        return ConfigurableReportData(
            data=page,
            columns=columns,
            total_records=total_records,
            id=report_config._id,
            domain=domain,
            get_params=bundle.request.GET,
            next_page=self._get_next_page(
                domain,
                report_config._id,
                start,
                limit,
                total_records,
                bundle.request.GET,
            )
        )

    def _get_report_configuration(self, id_, domain):
        """
        Fetch the required ReportConfiguration object
        :param id_: The id of the ReportConfiguration
        :param domain: The domain of the ReportConfiguration
        :return: A ReportConfiguration
        """
        try:
            if report_config_id_is_static(id_):
                return StaticReportConfiguration.by_id(id_, domain=domain)
            else:
                return get_document_or_not_found(ReportConfiguration, domain, id_)
        except DocumentNotFound:
            raise NotFound

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'domain': get_obj(bundle_or_obj).domain,
            'pk': get_obj(bundle_or_obj).id,
        }

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_list'):
        uri = super(ConfigurableReportDataResource, self).get_resource_uri(bundle_or_obj, url_name)
        if bundle_or_obj is not None and uri:
            get_params = get_obj(bundle_or_obj).get_params.copy()
            if "offset" not in get_params:
                get_params["offset"] = 0
            if "limit" not in get_params:
                get_params["limit"] = self.LIMIT_DEFAULT
            uri += "?{}".format(get_params.urlencode())
        return uri

    class Meta(CustomResourceMeta):
        list_allowed_methods = []
        detail_allowed_methods = ["get"]


class SimpleReportConfigurationResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    title = fields.CharField(readonly=True, attribute="title", null=True)
    filters = fields.ListField(readonly=True)
    columns = fields.ListField(readonly=True)

    def dehydrate_filters(self, bundle):
        obj_filters = bundle.obj.filters
        return [{
            "type": f["type"],
            "datatype": f["datatype"],
            "slug": f["slug"]
        } for f in obj_filters]

    def dehydrate_columns(self, bundle):
        obj_columns = bundle.obj.columns
        return [{
            "column_id": c['column_id'],
            "display": c['display'],
            "type": c["type"],
        } for c in obj_columns]

    def obj_get(self, bundle, **kwargs):
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            report_configuration = get_document_or_404(ReportConfiguration, domain, pk)
        except Http404 as e:
            raise NotFound(six.text_type(e))
        return report_configuration

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        return ReportConfiguration.by_domain(domain)

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'domain': get_obj(bundle_or_obj).domain,
            'pk': get_obj(bundle_or_obj)._id,
        }

    class Meta(CustomResourceMeta):
        list_allowed_methods = ["get"]
        detail_allowed_methods = ["get"]
        paginator_class = DoesNothingPaginator


UserDomain = namedtuple('UserDomain', 'domain_name project_name')
UserDomain.__new__.__defaults__ = ('', '')


class UserDomainsResource(Resource):
    domain_name = fields.CharField(attribute='domain_name')
    project_name = fields.CharField(attribute='project_name')

    class Meta(object):
        resource_name = 'user_domains'
        authentication = ApiKeyAuthentication()
        object_class = UserDomain
        include_resource_uri = False

    def dispatch_list(self, request, **kwargs):
        try:
            return super(UserDomainsResource, self).dispatch_list(request, **kwargs)
        except ImmediateHttpResponse as immediate_http_response:
            if isinstance(immediate_http_response.response, HttpUnauthorized):
                raise ImmediateHttpResponse(
                    response=HttpUnauthorized(
                        content='Username or API Key is incorrect', content_type='text/plain'
                    )
                )
            else:
                raise

    def obj_get_list(self, bundle, **kwargs):
        return self.get_object_list(bundle.request)

    def get_object_list(self, request):
        couch_user = CouchUser.from_django_user(request.user)
        results = []
        for domain in couch_user.get_domains():
            if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION):
                continue
            domain_object = Domain.get_by_name(domain)
            results.append(UserDomain(
                domain_name=domain_object.name,
                project_name=domain_object.hr_name or domain_object.name
            ))
        return results


Form = namedtuple('Form', 'form_xmlns form_name')
Form.__new__.__defaults__ = ('', '')


class DomainForms(Resource):
    """
    Returns: list of forms for a given domain with form name formatted for display in Zapier
    """
    form_xmlns = fields.CharField(attribute='form_xmlns')
    form_name = fields.CharField(attribute='form_name')

    class Meta(object):
        resource_name = 'domain_forms'
        authentication = ApiKeyAuthentication()
        object_class = Form
        include_resource_uri = False
        allowed_methods = ['get']

    def obj_get_list(self, bundle, **kwargs):
        application_id = bundle.request.GET.get('application_id')
        if not application_id:
            raise NotFound('application_id parameter required')

        domain = kwargs['domain']
        couch_user = CouchUser.from_django_user(bundle.request.user)
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION) or not couch_user.is_member_of(domain):
            raise ImmediateHttpResponse(
                HttpForbidden('You are not allowed to get list of forms for this domain')
            )

        results = []
        application = Application.get(docid=application_id)
        if not application:
            return []
        forms_objects = application.get_forms(bare=False)

        for form_object in forms_objects:
            form = form_object['form']
            module = form_object['module']
            form_name = '{} > {} > {}'.format(application.name, module.default_name(), form.default_name())
            results.append(Form(form_xmlns=form.xmlns, form_name=form_name))
        return results

# Zapier requires id and name; case_type has no obvious id, placeholder inserted instead.
CaseType = namedtuple('CaseType', 'case_type placeholder')
CaseType.__new__.__defaults__ = ('', '')


class DomainCases(Resource):
    """
    Returns: list of case types for a domain

    Note: only returns case types for which at least one case has been made
    """
    placeholder = fields.CharField(attribute='placeholder')
    case_type = fields.CharField(attribute='case_type')

    class Meta(object):
        resource_name = 'domain_cases'
        authentication = ApiKeyAuthentication()
        object_class = CaseType
        include_resource_uri = False
        allowed_methods = ['get']

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        couch_user = CouchUser.from_django_user(bundle.request.user)
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION) or not couch_user.is_member_of(domain):
            raise ImmediateHttpResponse(
                HttpForbidden('You are not allowed to get list of case types for this domain')
            )

        case_types = get_case_types_for_domain_es(domain)
        results = [CaseType(case_type=case_type) for case_type in case_types]
        return results


UserInfo = namedtuple('UserInfo', 'user_id user_name')
UserInfo.__new__.__defaults__ = ('', '')


class DomainUsernames(Resource):
    """
    Returns: list of usernames for a domain.
    """
    user_id = fields.CharField(attribute='user_id')
    user_name = fields.CharField(attribute='user_name')

    class Meta(object):
        resource_name = 'domain_usernames'
        authentication = ApiKeyAuthentication()
        object_class = User
        include_resource_uri = False
        allowed_methods = ['get']

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']

        couch_user = CouchUser.from_django_user(bundle.request.user)
        if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION) or not couch_user.is_member_of(domain):
            raise ImmediateHttpResponse(
                HttpForbidden('You are not allowed to get list of usernames for this domain')
            )
        user_ids_username_pairs = get_all_user_id_username_pairs_by_domain(domain)

        results = [UserInfo(user_id=user_pair[0], user_name=raw_username(user_pair[1]))
                   for user_pair in user_ids_username_pairs]
        return results


ODATA_CASE_RESOURCE_NAME = 'Cases'


class DeprecatedODataCaseResource(v0_4.CommCareCaseResource):

    case_type = None

    def dispatch(self, request_type, request, **kwargs):
        if not toggles.ODATA.enabled_for_request(request):
            raise ImmediateHttpResponse(response=HttpResponseNotFound('Feature flag not enabled.'))
        self.case_type = kwargs['case_type']
        return super(DeprecatedODataCaseResource, self).dispatch(request_type, request, **kwargs)

    def determine_format(self, request):
        # json only
        return 'application/json'

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        # populate the domain which is required by the serializer
        data['domain'] = request.domain
        data['case_type'] = self.case_type
        data['api_path'] = request.path
        response = super(DeprecatedODataCaseResource, self).create_response(request, data, response_class,
                                                                            **response_kwargs)
        # adds required odata headers to the returned response
        return add_odata_headers(response)

    def obj_get_list(self, bundle, domain, **kwargs):
        elastic_query_set = super(DeprecatedODataCaseResource, self).obj_get_list(bundle, domain, **kwargs)
        elastic_query_set.payload['filter']['and'].append({'term': {'type.exact': self.case_type}})
        return elastic_query_set

    class Meta(v0_4.CommCareCaseResource.Meta):
        authentication = ODataAuthentication(Permissions.edit_data)
        resource_name = 'odata/{}'.format(ODATA_CASE_RESOURCE_NAME)
        serializer = DeprecatedODataCaseSerializer()
        max_limit = 10000  # This is for experimental purposes only.  TODO: set to a better value soon after testing

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<case_type>[\w\d_.-]+)/$" % self._meta.resource_name,
                self.wrap_view('dispatch_list'))
        ]


ODATA_XFORM_INSTANCE_RESOURCE_NAME = 'Forms'


class DeprecatedODataFormResource(v0_4.XFormInstanceResource):

    xmlns = None

    def dispatch(self, request_type, request, **kwargs):
        if not toggles.ODATA.enabled_for_request(request):
            raise ImmediateHttpResponse(response=HttpResponseNotFound('Feature flag not enabled.'))
        self.app_id = kwargs['app_id']
        self.xmlns = kwargs['xmlns']
        return super(DeprecatedODataFormResource, self).dispatch(request_type, request, **kwargs)

    def determine_format(self, request):
        # json only
        return 'application/json'

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        data['domain'] = request.domain
        data['app_id'] = self.app_id
        data['xmlns'] = self.xmlns
        data['api_path'] = request.path
        response = super(DeprecatedODataFormResource, self).create_response(
            request, data, response_class, **response_kwargs)
        return add_odata_headers(response)

    def obj_get_list(self, bundle, domain, **kwargs):
        elastic_query_set = super(DeprecatedODataFormResource, self).obj_get_list(bundle, domain, **kwargs)
        full_xmlns = 'http://openrosa.org/formdesigner/' + kwargs['xmlns']
        elastic_query_set.payload['filter']['and'].append({'term': {'xmlns.exact': full_xmlns}})
        return elastic_query_set

    class Meta(v0_4.XFormInstanceResource.Meta):
        authentication = ODataAuthentication(Permissions.edit_data)
        resource_name = 'odata/{}'.format(ODATA_XFORM_INSTANCE_RESOURCE_NAME)
        serializer = DeprecatedODataFormSerializer()
        max_limit = 10000  # This is for experimental purposes only.  TODO: set to a better value soon after testing

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<app_id>[\w\d_.-]+)/(?P<xmlns>[\w\d_.-]+)" % self._meta.resource_name,
                self.wrap_view('dispatch_list'))
        ]


class ODataCaseResource(HqBaseResource, DomainSpecificResourceMixin):

    config_id = None

    def dispatch(self, request_type, request, **kwargs):
        if not toggles.ODATA.enabled_for_request(request):
            raise ImmediateHttpResponse(response=HttpResponseNotFound('Feature flag not enabled.'))
        self.config_id = kwargs['config_id']
        with TimingContext() as timer:
            response = super(ODataCaseResource, self).dispatch(request_type, request, **kwargs)
        record_feed_access_in_datadog(request, self.config_id, timer.duration, response)
        return response

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        data['domain'] = request.domain
        data['config_id'] = self.config_id
        data['api_path'] = request.path
        response = super(ODataCaseResource, self).create_response(
            request, data, response_class, **response_kwargs)
        return add_odata_headers(response)

    def obj_get_list(self, bundle, domain, **kwargs):
        config = get_document_or_404(CaseExportInstance, domain, self.config_id)
        return get_case_export_base_query(domain, config.case_type)

    def detail_uri_kwargs(self, bundle_or_obj):
        # Not sure why this is required but the feed 500s without it
        return {
            'pk': get_obj(bundle_or_obj)['case_id']
        }

    class Meta(v0_4.CommCareCaseResource.Meta):
        authentication = ODataAuthentication(Permissions.edit_data)
        resource_name = 'odata/cases'
        serializer = ODataCaseSerializer()
        limit = 2000
        max_limit = 10000

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<config_id>[\w\d_.-]+)" % self._meta.resource_name,
                self.wrap_view('dispatch_list'))
        ]

    def determine_format(self, request):
        # Results should be sent as JSON
        return 'application/json'


class ODataFormResource(HqBaseResource, DomainSpecificResourceMixin):

    config_id = None

    def dispatch(self, request_type, request, **kwargs):
        if not toggles.ODATA.enabled_for_request(request):
            raise ImmediateHttpResponse(response=HttpResponseNotFound('Feature flag not enabled.'))
        self.config_id = kwargs['config_id']
        with TimingContext() as timer:
            response = super(ODataFormResource, self).dispatch(request_type, request, **kwargs)
        record_feed_access_in_datadog(request, self.config_id, timer.duration, response)
        return response

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        data['domain'] = request.domain
        data['config_id'] = self.config_id
        data['api_path'] = request.path
        response = super(ODataFormResource, self).create_response(
            request, data, response_class, **response_kwargs)
        return add_odata_headers(response)

    def obj_get_list(self, bundle, domain, **kwargs):
        config = get_document_or_404(FormExportInstance, domain, self.config_id)
        return get_form_export_base_query(domain, config.app_id, config.xmlns, include_errors=True)

    def detail_uri_kwargs(self, bundle_or_obj):
        # Not sure why this is required but the feed 500s without it
        return {
            'pk': get_obj(bundle_or_obj)['_id']
        }

    class Meta(v0_4.XFormInstanceResource.Meta):
        authentication = ODataAuthentication(Permissions.edit_data)
        resource_name = 'odata/forms'
        serializer = ODataFormSerializer()
        limit = 2000
        max_limit = 10000

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>%s)/(?P<config_id>[\w\d_.-]+)" % self._meta.resource_name,
                self.wrap_view('dispatch_list'))
        ]

    def determine_format(self, request):
        # Results should be sent as JSON
        return 'application/json'
