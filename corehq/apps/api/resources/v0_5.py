from django.http import Http404
from django.forms import ValidationError
from tastypie import http
from tastypie.authentication import ApiKeyAuthentication
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.exceptions import BadRequest, ImmediateHttpResponse, NotFound
from tastypie.http import HttpForbidden, HttpUnauthorized
from tastypie.paginator import Paginator
from tastypie.resources import convert_post_to_patch, ModelResource, Resource
from tastypie.utils import dict_strip_unicode_keys

from collections import namedtuple

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from tastypie import fields
from tastypie.bundle import Bundle

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.api.resources.auth import RequirePermissionAuthentication, AdminAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import get_obj
from corehq.apps.app_manager.models import Application
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.es import UserES

from casexml.apps.stock.models import StockTransaction
from corehq.apps.groups.models import Group
from corehq.apps.sms.util import strip_plus
from corehq.apps.userreports.models import ReportConfiguration, \
    StaticReportConfiguration, report_config_id_is_static
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.view import query_dict_to_dict, \
    get_filter_values
from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn
from corehq.apps.users.models import CommCareUser, WebUser, Permissions, CouchUser, UserRole
from corehq.util import get_document_or_404
from corehq.util.couch import get_document_or_not_found, DocumentNotFound

from . import v0_1, v0_4, CouchResourceMixin
from . import HqBaseResource, DomainSpecificResourceMixin
from phonelog.models import DeviceReportEntry
from itertools import chain


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
        return namedtuple('user', user.keys())(**user)

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
        fields = self.fields.keys()
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
        return map(self.to_obj, users)

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
                            bundle.obj.errors.append(e.message)
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
            except AssertionError as ex:
                status = http.HttpBadRequest
                bundle.data['_id'] = ex.message
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
        except AssertionError as ex:
            bundle.data['error_message'] = ex.message
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


class DomainAuthorization(ReadOnlyAuthorization):

    def __init__(self, domain_key='domain', *args, **kwargs):
        self.domain_key = domain_key

    def read_list(self, object_list, bundle):
        return object_list.filter(**{self.domain_key: bundle.request.domain})


class NoCountingPaginator(Paginator):
    """
    The default paginator contains the total_count value, which shows how
    many objects are in the underlying object list. Obtaining this data from
    the database is inefficient, especially with large datasets, and unfiltered API requests.

    This class does not perform any counting and return 'null' as the value of total_count.

    See:
        * http://django-tastypie.readthedocs.org/en/latest/paginator.html
        * http://wiki.postgresql.org/wiki/Slow_Counting
    """

    def get_previous(self, limit, offset):
        if offset - limit < 0:
            return None

        return self._generate_uri(limit, offset-limit)

    def get_next(self, limit, offset, count):
        """
        Always generate the next URL even if there may be no records.
        """
        return self._generate_uri(limit, offset+limit)

    def get_count(self):
        """
        Don't do any counting.
        """
        return None


class DeviceReportResource(HqBaseResource, ModelResource):

    class Meta:
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

    class Meta:
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
    ConfigurableReport view.
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
        report = ReportFactory.from_spec(report_config)

        filter_values = get_filter_values(
            report_config.ui_filters,
            query_dict_to_dict(get_params, domain)
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


class DoesNothingPaginator(Paginator):
    def page(self):
        return {
            self.collection_name: self.objects,
            "meta": {'total_count': self.get_count()}
        }


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
            raise NotFound(e.message)
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

    class Meta:
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
    form_xmlns = fields.CharField(attribute='form_xmlns')
    form_name = fields.CharField(attribute='form_name')

    class Meta:
        resource_name = 'domain_forms'
        authentication = ApiKeyAuthentication()
        object_class = Form
        include_resource_uri = False

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
            form_name = '{} > {} > {}'.format(application.name, module.name['en'], form.name['en'])
            results.append(Form(form_xmlns=form.xmlns, form_name=form_name))
        return results
