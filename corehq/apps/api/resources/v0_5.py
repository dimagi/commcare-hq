import dataclasses
import functools
import json
from base64 import b64decode, b64encode
from collections import namedtuple
from dataclasses import InitVar, dataclass
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.urls import re_path as url
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Max, Min, Q
from django.db.models.functions import TruncDate
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseBadRequest,
    JsonResponse,
    QueryDict,
)
from django.test import override_settings
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop
from django.views.decorators.csrf import csrf_exempt

import pytz
from memoized import memoized_property
from tastypie import fields, http
from tastypie.authorization import ReadOnlyAuthorization
from tastypie.bundle import Bundle
from tastypie.exceptions import BadRequest, ImmediateHttpResponse, NotFound
from tastypie.http import HttpForbidden, HttpUnauthorized
from tastypie.resources import ModelResource, Resource


from phonelog.models import DeviceReportEntry

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.api.cors import add_cors_headers_to_response
from corehq.apps.api.decorators import allow_cors, api_throttle
from corehq.apps.api.odata.serializers import (
    ODataCaseSerializer,
    ODataFormSerializer,
)
from corehq.apps.api.odata.utils import record_feed_access_in_datadog
from corehq.apps.api.odata.views import (
    add_odata_headers,
    raise_odata_permissions_issues,
)
from corehq.apps.api.resources.auth import (
    LoginAuthentication,
    ODataAuthentication,
    RequirePermissionAuthentication,
)
from corehq.apps.api.resources.messaging_event.utils import get_request_params
from corehq.apps.api.resources.meta import (
    AdminResourceMeta,
    CustomResourceMeta,
)
from corehq.apps.api.resources.serializers import ListToSingleObjectSerializer
from corehq.apps.api.util import (
    django_date_filter,
    get_obj,
    make_date_filter,
    parse_str_to_date,
    cursor_based_query_for_datasource
)
from corehq.apps.app_manager.models import Application
from corehq.apps.auditcare.models import NavigationEventAudit
from corehq.apps.case_importer.views import require_can_edit_data
from corehq.apps.domain.decorators import api_auth
from corehq.apps.domain.models import Domain
from corehq.apps.es import UserES
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.groups.models import Group
from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.analytics.esaccessors import (
    get_case_types_for_domain_es,
)
from corehq.apps.reports.standard.cases.utils import (
    query_location_restricted_cases,
    query_location_restricted_forms,
)
from corehq.apps.userreports.columns import UCRExpandDatabaseSubcolumn
from corehq.apps.userreports.dbaccessors import get_datasources_for_domain
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
    StaticReportConfiguration,
    get_datasource_config,
    report_config_id_is_static,
)
from corehq.apps.userreports.reports.data_source import (
    ConfigurableReportDataSource,
)
from corehq.apps.userreports.reports.view import (
    get_filter_values,
    query_dict_to_dict,
)
from corehq.apps.userreports.util import (
    get_configurable_and_static_reports,
    get_indicator_adapter,
    get_report_config_or_not_found,
)
from corehq.apps.users.dbaccessors import (
    get_all_user_id_username_pairs_by_domain,
    get_user_id_by_username,
)
from corehq.apps.users.models import (
    CommCareUser,
    ConnectIDUserLink,
    CouchUser,
    HqPermissions,
    WebUser,
)
from corehq.apps.users.util import generate_mobile_username, raw_username
from corehq.const import USER_CHANGE_VIA_API
from corehq.util import get_document_or_404
from corehq.util.couch import DocumentNotFound
from corehq.util.timer import TimingContext

from ..exceptions import UpdateUserException
from ..user_updates import update
from . import (
    CorsResourceMixin,
    CouchResourceMixin,
    DomainSpecificResourceMixin,
    HqBaseResource,
    v0_1,
    v0_4,
)
from .pagination import DoesNothingPaginator, NoCountingPaginator, response_for_cursor_based_pagination


MOCK_BULK_USER_ES = None
EXPORT_DATASOURCE_DEFAULT_PAGINATION_LIMIT = 1000
EXPORT_DATASOURCE_MAX_PAGINATION_LIMIT = 10000


def user_es_call(domain, q, fields, size, start_at):
    query = (UserES()
             .domain(domain)
             .fields(fields)
             .size(size)
             .start(start_at))
    if q is not None:
        query.set_query({"query_string": {"query": q}})
    return query.run().hits


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
        authentication = RequirePermissionAuthentication(HqPermissions.edit_commcare_users)
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

        def param(p):
            return params.get(p, None)

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

    def obj_create(self, bundle, **kwargs):
        try:
            username = generate_mobile_username(bundle.data['username'], kwargs['domain'])
        except ValidationError as e:
            raise BadRequest(e.message)

        if not (bundle.data.get('password') or bundle.data.get('connect_username')):
            raise BadRequest(_('Password or connect username required'))

        if bundle.data.get('connect_username') and not toggles.COMMCARE_CONNECT.enabled(kwargs['domain']):
            raise BadRequest(_("You don't have permission to use connect_username field"))

        try:
            bundle.obj = CommCareUser.create(
                domain=kwargs['domain'],
                username=username,
                password=bundle.data.get('password'),
                created_by=bundle.request.couch_user,
                created_via=USER_CHANGE_VIA_API,
                email=bundle.data.get('email', '').lower(),
            )
            # password was just set
            bundle.data.pop('password', None)
            # do not call update with username key
            bundle.data.pop('username', None)
            self._update(bundle)
            bundle.obj.save()
        except Exception:
            if bundle.obj._id:
                bundle.obj.retire(bundle.request.domain, deleted_by=bundle.request.couch_user,
                                  deleted_via=USER_CHANGE_VIA_API)
            try:
                django_user = bundle.obj.get_django_user()
            except User.DoesNotExist:
                pass
            else:
                django_user.delete()
            raise
        if bundle.data.get('connect_username'):
            ConnectIDUserLink.objects.create(
                domain=bundle.request.domain,
                connectid_username=bundle.data['connect_username'],
                commcare_user=bundle.obj.get_django_user()
            )
        return bundle

    def obj_update(self, bundle, **kwargs):
        bundle.obj = CommCareUser.get(kwargs['pk'])
        assert bundle.obj.domain == kwargs['domain']
        user_change_logger = self._get_user_change_logger(bundle)
        errors = self._update(bundle, user_change_logger)
        if errors:
            formatted_errors = ', '.join(errors)
            raise BadRequest(_('The request resulted in the following errors: {}').format(formatted_errors))
        assert bundle.obj.domain == kwargs['domain']
        bundle.obj.save()
        user_change_logger.save()
        return bundle

    def obj_delete(self, bundle, **kwargs):
        user = CommCareUser.get(kwargs['pk'])
        if user:
            user.retire(bundle.request.domain, deleted_by=bundle.request.couch_user,
                        deleted_via=USER_CHANGE_VIA_API)
        return ImmediateHttpResponse(response=http.HttpAccepted())

    @classmethod
    def _update(cls, bundle, user_change_logger=None):
        errors = []
        for key, value in bundle.data.items():
            try:
                update(bundle.obj, key, value, user_change_logger)
            except UpdateUserException as e:
                errors.append(e.message)

        return errors


class WebUserResource(v0_1.WebUserResource):

    def get_resource_uri(self, bundle_or_obj=None, url_name='api_dispatch_detail'):
        if bundle_or_obj is None:
            return super().get_resource_uri(None, url_name)
        return reverse('api_dispatch_detail', kwargs={
            'resource_name': self._meta.resource_name,
            'domain': bundle_or_obj.request.domain,
            'api_name': self._meta.api_name,
            'pk': bundle_or_obj.obj._id,
        })


class AdminWebUserResource(v0_1.UserResource):
    domains = fields.ListField(attribute='domains')

    def obj_get(self, bundle, **kwargs):
        return WebUser.get(kwargs['pk'])

    def obj_get_list(self, bundle, **kwargs):
        if 'username' in bundle.request.GET:
            web_user = WebUser.get_by_username(bundle.request.GET['username'])
            return [web_user] if web_user.is_active else []
        return [WebUser.wrap(u) for u in UserES().web_users().run().hits]

    class Meta(AdminResourceMeta):
        detail_allowed_methods = ['get']
        list_allowed_methods = ['get']
        object_class = WebUser
        resource_name = 'web-user'


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
        return super().patch_list_replica(self.obj_create, request, **kwargs)

    def post_list(self, request, **kwargs):
        """
        Exactly copied from https://github.com/toastdriven/django-tastypie/blob/v0.9.14/tastypie/resources.py#L1314
        (BSD licensed) and modified to catch Exception and not returning traceback
        """
        deserialized = self.deserialize(request, request.body,
                                        format=request.META.get('CONTENT_TYPE', 'application/json'))
        deserialized = self.alter_deserialized_detail_data(request, deserialized)
        bundle = self.build_bundle(data=deserialized, request=request)
        try:
            updated_bundle = self.obj_create(bundle, **self.remove_api_resource_names(kwargs))
            location = self.get_resource_uri(updated_bundle)

            if not self._meta.always_return_data:
                return http.HttpCreated(location=location)
            else:
                updated_bundle = self.full_dehydrate(updated_bundle)
                updated_bundle = self.alter_detail_data_to_serialize(request, updated_bundle)
                return self.create_response(request, updated_bundle, response_class=http.HttpCreated,
                                            location=location)
        except AssertionError as e:
            bundle.data['error_message'] = str(e)
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
        return self._get_resource_uri(obj)

    def _get_resource_uri(self, obj):
        # This function is called up to 1000 times per request
        # so build url from a known string template
        # to avoid calling the expensive `reverse` function each time
        return self._get_resource_uri_template.format(domain=obj.domain, pk=obj._id)

    @memoized_property
    def _get_resource_uri_template(self):
        """Returns the literal string "/a/{domain}/api/v0.5/group/{pk}/" in a DRY way"""
        return reverse('api_dispatch_detail', kwargs=dict(
            resource_name=self._meta.resource_name,
            api_name=self._meta.api_name,
            domain='__domain__',
            pk='__pk__')).replace('__pk__', '{pk}').replace('__domain__', '{domain}')

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
        authentication = RequirePermissionAuthentication(HqPermissions.edit_data)
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

    def _get_report_data(self, report_config, domain, start, limit, get_params, couch_user):
        report = ConfigurableReportDataSource.from_spec(report_config, include_prefilters=True)

        string_type_params = [
            filter.name
            for filter in report_config.ui_filters
            if getattr(filter, 'datatype', 'string') == "string"
        ]
        filter_values = get_filter_values(
            report_config.ui_filters,
            query_dict_to_dict(get_params, domain, string_type_params),
            couch_user,
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
            report_config, domain, start, limit, bundle.request.GET, bundle.request.couch_user)

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
                return get_report_config_or_not_found(domain, id_)
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
        authentication = RequirePermissionAuthentication(HqPermissions.view_reports, allow_session_auth=True)
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
            raise NotFound(str(e))
        return report_configuration

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        return get_configurable_and_static_reports(domain)

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'domain': get_obj(bundle_or_obj).domain,
            'pk': get_obj(bundle_or_obj)._id,
        }

    class Meta(CustomResourceMeta):
        list_allowed_methods = ["get"]
        detail_allowed_methods = ["get"]
        paginator_class = DoesNothingPaginator


class DataSourceConfigurationResource(CouchResourceMixin, HqBaseResource, DomainSpecificResourceMixin):
    """
    API resource for DataSourceConfigurations (UCR data sources)
    """
    id = fields.CharField(attribute='get_id', readonly=True, unique=True)
    display_name = fields.CharField(attribute="display_name", null=True)
    configured_filter = fields.DictField(attribute="configured_filter", use_in='detail')
    configured_indicators = fields.ListField(attribute="configured_indicators", use_in='detail')

    def _ensure_toggle_enabled(self, request):
        if not toggles.USER_CONFIGURABLE_REPORTS.enabled_for_request(request):
            raise ImmediateHttpResponse(
                add_cors_headers_to_response(
                    HttpResponse(
                        json.dumps({"error": _("You don't have permission to access this API")}),
                        content_type="application/json",
                        status=401,
                    )
                )
            )

    def obj_get(self, bundle, **kwargs):
        self._ensure_toggle_enabled(bundle.request)
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            data_source = get_document_or_404(DataSourceConfiguration, domain, pk)
        except Http404 as e:
            raise NotFound(str(e))
        return data_source

    def obj_get_list(self, bundle, **kwargs):
        self._ensure_toggle_enabled(bundle.request)
        domain = kwargs['domain']
        return get_datasources_for_domain(domain)

    def obj_update(self, bundle, **kwargs):
        self._ensure_toggle_enabled(bundle.request)
        domain = kwargs['domain']
        pk = kwargs['pk']
        try:
            data_source = get_document_or_404(DataSourceConfiguration, domain, pk)
        except Http404 as e:
            raise NotFound(str(e))
        allowed_update_fields = [
            'display_name',
            'configured_filter',
            'configured_indicators',
        ]
        for key, value in bundle.data.items():
            if key in allowed_update_fields:
                data_source[key] = value
        try:
            data_source.validate()
            data_source.save()
        except BadSpecError as e:
            raise ImmediateHttpResponse(
                add_cors_headers_to_response(
                    HttpResponse(
                        json.dumps({"error": _("Invalid data source! Details: {details}").format(details=str(e))}),
                        content_type="application/json",
                        status=500,
                    )
                )
            )
        bundle.obj = data_source
        return bundle

    def detail_uri_kwargs(self, bundle_or_obj):
        return {
            'domain': get_obj(bundle_or_obj).domain,
            'pk': get_obj(bundle_or_obj)._id,
        }

    class Meta(CustomResourceMeta):
        resource_name = 'ucr_data_source'
        list_allowed_methods = ['get']
        detail_allowed_methods = ['get', 'put']
        always_return_data = True
        paginator_class = DoesNothingPaginator
        authentication = RequirePermissionAuthentication(HqPermissions.edit_ucrs)


UserDomain = namedtuple('UserDomain', 'domain_name project_name')
UserDomain.__new__.__defaults__ = ('', '')


class UserDomainsResource(CorsResourceMixin, Resource):
    domain_name = fields.CharField(attribute='domain_name')
    project_name = fields.CharField(attribute='project_name')

    class Meta(object):
        resource_name = 'user_domains'
        authentication = LoginAuthentication(allow_session_auth=True)
        object_class = UserDomain
        include_resource_uri = False

    def dispatch_list(self, request, **kwargs):
        try:
            return super(UserDomainsResource, self).dispatch_list(request, **kwargs)
        except ImmediateHttpResponse as immediate_http_response:
            if isinstance(immediate_http_response.response, HttpUnauthorized):
                raise ImmediateHttpResponse(
                    response=HttpUnauthorized(
                        content='Username or API Key is incorrect, expired or deactivated',
                        content_type='text/plain'
                    )
                )
            else:
                raise

    def obj_get_list(self, bundle, **kwargs):
        return self.get_object_list(bundle.request)

    def get_object_list(self, request):
        feature_flag = request.GET.get("feature_flag")
        if feature_flag and feature_flag not in toggles.all_toggle_slugs():
            raise BadRequest(f"{feature_flag!r} is not a valid feature flag")
        can_view_reports = request.GET.get("can_view_reports")
        couch_user = CouchUser.from_django_user(request.user)
        username = request.user.username
        results = []
        for domain in couch_user.get_domains():
            if not domain_has_privilege(domain, privileges.ZAPIER_INTEGRATION):
                continue
            domain_object = Domain.get_by_name(domain)
            if feature_flag and feature_flag not in toggles.toggles_dict(username=username, domain=domain):
                continue
            if can_view_reports and not couch_user.can_view_reports(domain):
                continue
            results.append(UserDomain(
                domain_name=domain_object.name,
                project_name=domain_object.hr_name or domain_object.name
            ))
        return results


class IdentityResource(CorsResourceMixin, Resource):
    id = fields.CharField(attribute='get_id', readonly=True)
    username = fields.CharField(attribute='username', readonly=True)
    first_name = fields.CharField(attribute='first_name', readonly=True)
    last_name = fields.CharField(attribute='last_name', readonly=True)
    email = fields.CharField(attribute='email', readonly=True)

    def obj_get_list(self, bundle, **kwargs):
        return [bundle.request.couch_user]

    class Meta(object):
        resource_name = 'identity'
        authentication = LoginAuthentication()
        serializer = ListToSingleObjectSerializer()
        detail_allowed_methods = []
        list_allowed_methods = ['get']
        object_class = CouchUser
        include_resource_uri = False


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
        authentication = RequirePermissionAuthentication(HqPermissions.access_api)
        object_class = Form
        include_resource_uri = False
        allowed_methods = ['get']
        limit = 200
        max_limit = 1000

    def obj_get_list(self, bundle, **kwargs):
        application_id = bundle.request.GET.get('application_id')
        if not application_id:
            raise NotFound('application_id parameter required')

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
        authentication = RequirePermissionAuthentication(HqPermissions.access_api)
        object_class = CaseType
        include_resource_uri = False
        allowed_methods = ['get']
        limit = 100
        max_limit = 1000

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
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
        authentication = RequirePermissionAuthentication(HqPermissions.view_commcare_users)
        object_class = User
        include_resource_uri = False
        allowed_methods = ['get']

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        user_ids_username_pairs = get_all_user_id_username_pairs_by_domain(domain)
        results = [UserInfo(user_id=user_pair[0], user_name=raw_username(user_pair[1]))
                   for user_pair in user_ids_username_pairs]
        return results


class BaseODataResource(HqBaseResource, DomainSpecificResourceMixin):

    def dispatch(self, request_type, request, **kwargs):
        if not domain_has_privilege(request.domain, privileges.ODATA_FEED):
            raise ImmediateHttpResponse(
                response=HttpResponseNotFound('Feature flag not enabled.')
            )
        with TimingContext() as timer:
            response = super(BaseODataResource, self).dispatch(
                request_type, request, **kwargs
            )
        record_feed_access_in_datadog(request, kwargs['config_id'], timer.duration, response)
        return response

    def create_response(self, request, data, response_class=HttpResponse,
                        **response_kwargs):
        data['domain'] = request.domain
        data['api_path'] = request.path
        # Avoids storing these properties on the class instance which protects against the possibility of
        # concurrent requests making conflicting updates to properties
        data['config_id'] = request.resolver_match.kwargs['config_id']
        data['table_id'] = int(request.resolver_match.kwargs.get('table_id', 0))
        response = super(BaseODataResource, self).create_response(
            request, data, response_class, **response_kwargs)
        return add_odata_headers(response)

    def detail_uri_kwargs(self, bundle_or_obj):
        # Not sure why this is required but the feed 500s without it
        return {
            'pk': get_obj(bundle_or_obj)['_id']
        }

    def determine_format(self, request):
        # Results should be sent as JSON
        return 'application/json'


@location_safe
class ODataCaseResource(BaseODataResource):

    def obj_get_list(self, bundle, domain, **kwargs):
        config = get_document_or_404(CaseExportInstance, domain, kwargs['config_id'])
        if raise_odata_permissions_issues(bundle.request.couch_user, domain, config):
            raise ImmediateHttpResponse(
                HttpForbidden(gettext_noop(
                    "You do not have permission to view this feed."
                ))
            )

        query = config.get_query()

        if not bundle.request.couch_user.has_permission(
            domain, 'access_all_locations'
        ):
            query = query_location_restricted_cases(
                query,
                bundle.request.domain,
                bundle.request.couch_user,
            )

        return query

    class Meta(v0_4.CommCareCaseResource.Meta):
        authentication = ODataAuthentication()
        resource_name = 'odata/cases'
        serializer = ODataCaseSerializer()
        limit = 2000
        max_limit = 10000

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>{})/(?P<config_id>[\w\d_.-]+)/(?P<table_id>[\d]+)/feed".format(
                self._meta.resource_name), self.wrap_view('dispatch_list')),
            url(r"^(?P<resource_name>{})/(?P<config_id>[\w\d_.-]+)/feed".format(
                self._meta.resource_name), self.wrap_view('dispatch_list')),
        ]


@location_safe
class ODataFormResource(BaseODataResource):

    def obj_get_list(self, bundle, domain, **kwargs):
        config = get_document_or_404(FormExportInstance, domain, kwargs['config_id'])
        if raise_odata_permissions_issues(bundle.request.couch_user, domain, config):
            raise ImmediateHttpResponse(
                HttpForbidden(gettext_noop(
                    "You do not have permission to view this feed."
                ))
            )

        query = config.get_query()

        if not bundle.request.couch_user.has_permission(
            domain, 'access_all_locations'
        ):
            query = query_location_restricted_forms(
                query,
                bundle.request.domain,
                bundle.request.couch_user,
            )

        return query

    class Meta(v0_4.XFormInstanceResource.Meta):
        authentication = ODataAuthentication()
        resource_name = 'odata/forms'
        serializer = ODataFormSerializer()
        limit = 2000
        max_limit = 10000

    def prepend_urls(self):
        return [
            url(r"^(?P<resource_name>{})/(?P<config_id>[\w\d_.-]+)/(?P<table_id>[\d]+)/feed".format(
                self._meta.resource_name), self.wrap_view('dispatch_list')),
            url(r"^(?P<resource_name>{})/(?P<config_id>[\w\d_.-]+)/feed".format(
                self._meta.resource_name), self.wrap_view('dispatch_list')),
        ]


@dataclass
class NavigationEventAuditResourceParams:
    domain: InitVar
    default_limit: InitVar
    max_limit: InitVar
    raw_params: InitVar = None

    users: list[str] = dataclasses.field(default_factory=list)
    limit: int = None
    local_timezone: str = None
    cursor: str = None
    local_date: dict[str:str] = dataclasses.field(default_factory=dict)
    cursor_local_date: str = None
    cursor_user: str = None
    UTC_start_time_start: datetime = None
    UTC_start_time_end: datetime = None

    def __post_init__(self, domain, default_limit, max_limit, raw_params=None):
        if raw_params:
            self.cursor = raw_params.get('cursor')
            if self.cursor:
                raw_params = self._process_cursor()
            self._validate_keys(raw_params)

            self._set_compound_keys(raw_params)
            self.limit = raw_params.get('limit')
            self.users = raw_params.getlist('users')
            self.local_timezone = raw_params.get('local_timezone')
            self.UTC_start_time_start = raw_params.get('UTC_start_time_start')
            self.UTC_start_time_end = raw_params.get('UTC_start_time_end')

        if self.limit:
            self._process_limit(default_limit, max_limit)
        if self.UTC_start_time_start:
            self.UTC_start_time_start = parse_str_to_date(self.UTC_start_time_start)
        if self.UTC_start_time_end:
            self.UTC_start_time_end = parse_str_to_date(self.UTC_start_time_end)
        self._process_local_timezone(domain)

    def _validate_keys(self, params):
        valid_keys = {'users', 'limit', 'local_timezone', 'cursor', 'format', 'local_date',
                    'UTC_start_time_start', 'UTC_start_time_end'}
        standardized_keys = set()

        for key in params.keys():
            if '.' in key:
                key, qualifier = key.split('.', maxsplit=1)
            standardized_keys.add(key)

        invalid_keys = standardized_keys - valid_keys
        if invalid_keys:
            raise ValueError(f"Invalid parameter(s): {', '.join(invalid_keys)}")

    def _set_compound_keys(self, params):
        local_date = {}
        for key in params.keys():
            if '.' in key:
                prefix, qualifier = key.split('.', maxsplit=1)
                if prefix == 'local_date':
                    local_date[qualifier] = params.get(key)

        self.local_date = local_date

    def _process_limit(self, default_limit, max_limit):
        try:
            self.limit = int(self.limit) or default_limit
            if self.limit < 0:
                raise ValueError
        except (ValueError, TypeError):
            raise BadRequest(_('limit must be a positive integer.'))

        if self.limit > max_limit:
            raise BadRequest(_('Limit may not exceed {}.').format(max_limit))

    def _process_cursor(self):
        cursor_params_string = b64decode(self.cursor).decode('utf-8')
        cursor_params = QueryDict(cursor_params_string, mutable=True)
        self.cursor_local_date = cursor_params.pop('cursor_local_date', [None])[0]
        self.cursor_user = cursor_params.pop('cursor_user', [None])[0]
        return cursor_params

    def _process_local_timezone(self, domain):
        if self.local_timezone is None:
            self.local_timezone = Domain.get_by_name(domain).get_default_timezone()
        elif isinstance(self.local_timezone, str):
            self.local_timezone = pytz.timezone(self.local_timezone)


class NavigationEventAuditResource(HqBaseResource, Resource):
    local_date = fields.DateField(attribute='local_date', readonly=True)
    UTC_start_time = fields.DateTimeField(attribute='UTC_start_time', readonly=True)
    UTC_end_time = fields.DateTimeField(attribute='UTC_end_time', readonly=True)
    user = fields.CharField(attribute='user', readonly=True)

    class Meta:
        authentication = RequirePermissionAuthentication(HqPermissions.view_web_users)
        queryset = NavigationEventAudit.objects.all()
        resource_name = 'action_times'
        include_resource_uri = False
        allowed_methods = ['get']
        detail_allowed_methods = []
        limit = 10000
        max_limit = 10000

    # Compound filters take the form `prefix.qualifier=value`
    # These filter functions are called with qualifier and value
    COMPOUND_FILTERS = {
        'local_date': make_date_filter(functools.partial(django_date_filter, field_name='local_date'))
    }

    @staticmethod
    def to_obj(action_times):
        '''
        Takes a flat dict and returns an object
        '''
        return namedtuple('action_times', list(action_times))(**action_times)

    def dispatch(self, request_type, request, **kwargs):
        #super needs to be called first to authenticate user. Otherwise request.user returns AnonymousUser
        response = super(HqBaseResource, self).dispatch(request_type, request, **kwargs)
        if not toggles.ACTION_TIMES_API.enabled_for_request(request):
            msg = (_("You don't have permission to access this API"))
            raise ImmediateHttpResponse(JsonResponse({"error": msg}, status=403))
        else:
            return response

    def alter_list_data_to_serialize(self, request, data):
        data['meta']['local_date_timezone'] = self.api_params.local_timezone.zone
        data['meta']['total_count'] = self.count

        original_params = request.GET
        if 'cursor' in original_params:
            params_string = b64decode(original_params['cursor']).decode('utf-8')
            cursor_params = QueryDict(params_string, mutable=True)
            if 'limit' in cursor_params:
                data['meta']['limit'] = int(cursor_params['limit'])
        else:
            cursor_params = original_params.copy()

        if data['meta']['total_count'] > data['meta']['limit']:
            last_object = data['objects'][-1]
            cursor_params['cursor_local_date'] = last_object.data['local_date']
            cursor_params['cursor_user'] = last_object.data['user']
            encoded_cursor = b64encode(urlencode(cursor_params).encode('utf-8'))

            next_params = {'cursor': encoded_cursor}

            next_url = f'?{urlencode(next_params)}'
            data['meta']['next'] = next_url
        return data

    def dehydrate(self, bundle):
        bundle.data['user_id'] = get_user_id_by_username(bundle.data['user'])
        return bundle

    def obj_get_list(self, bundle, **kwargs):
        domain = kwargs['domain']
        self.api_params = NavigationEventAuditResourceParams(raw_params=bundle.request.GET, domain=domain,
                                                             default_limit=self._meta.limit,
                                                             max_limit=self._meta.max_limit)
        results = self.cursor_query(domain, self.api_params)
        return list(map(self.to_obj, results))

    @classmethod
    def cursor_query(cls, domain: str, params: NavigationEventAuditResourceParams) -> list:
        if not params.limit:
            params.limit = cls._meta.limit
        queryset = cls._query(domain, params)

        cursor_local_date = params.cursor_local_date
        cursor_user = params.cursor_user

        if cursor_local_date and cursor_user:
            queryset = queryset.filter(
                Q(local_date__gt=cursor_local_date)
                | (Q(local_date=cursor_local_date) & Q(user__gt=cursor_user))
            )

        queryset = queryset.annotate(UTC_start_time=Min('event_date'), UTC_end_time=Max('event_date'))

        if params.UTC_start_time_start:
            queryset = queryset.filter(UTC_start_time__gte=params.UTC_start_time_start)
        if params.UTC_start_time_end:
            queryset = queryset.filter(UTC_start_time__lte=params.UTC_start_time_end)

        with override_settings(USE_TZ=True):
            cls.count = queryset.count()
            # TruncDate ignores tzinfo if the queryset is not evaluated within overridden USE_TZ setting
            return list(queryset[:params.limit])

    @classmethod
    def _query(cls, domain: str, params: NavigationEventAuditResourceParams):
        queryset = NavigationEventAudit.objects.filter(domain=domain)
        if params.users:
            queryset = queryset.filter(user__in=params.users)

        # Initial approximate filtering for performance. The largest time difference between local timezone and UTC
        # is <24 hours so items outside that bound will not be within the eventual local_date grouping.
        approx_time_offset = timedelta(hours=24)
        if params.UTC_start_time_start:
            offset_UTC_start_time_start = params.UTC_start_time_start - approx_time_offset
            queryset = queryset.filter(event_date__gte=offset_UTC_start_time_start)
        if params.UTC_start_time_end:
            offset_UTC_start_time_end = params.UTC_start_time_end + approx_time_offset
            queryset = queryset.filter(event_date__lte=offset_UTC_start_time_end)

        local_date_filter = cls._get_compound_filter('local_date', params)

        results = (queryset
                .exclude(user__isnull=True)
                .annotate(local_date=TruncDate('event_date', tzinfo=params.local_timezone))
                .filter(local_date_filter)
                .values('local_date', 'user'))

        results = results.order_by('local_date', 'user')

        return results

    @classmethod
    def _get_compound_filter(cls, param_field_name: str, params: NavigationEventAuditResourceParams):
        compound_filter = Q()
        if param_field_name in cls.COMPOUND_FILTERS:
            for qualifier, val in getattr(params, param_field_name).items():
                filter_obj = cls.COMPOUND_FILTERS[param_field_name](qualifier, val)
                compound_filter &= Q(**filter_obj)
        return compound_filter


@csrf_exempt
@allow_cors(['GET'])
@api_auth()
@require_can_edit_data
@requires_privilege_with_fallback(privileges.API_ACCESS)
@api_throttle
def get_ucr_data(request, domain):
    if not toggles.EXPORT_DATA_SOURCE_DATA.enabled(domain):
        return HttpResponseForbidden()
    try:
        if request.method == 'GET':
            config_id = request.GET.get("data_source_id")
            if not config_id:
                return HttpResponseBadRequest("Missing data_source_id parameter")
            return get_datasource_data(request, config_id, domain)
        return JsonResponse({'error': "Request method not allowed"}, status=405)
    except BadRequest as e:
        return JsonResponse({'error': str(e)}, status=400)


def get_datasource_data(request, config_id, domain):
    """Fetch data of the datasource specified by `config_id` in a paginated manner"""
    config, _ = get_datasource_config(config_id, domain)
    datasource_adapter = get_indicator_adapter(config, load_source='export_data_source')
    request_params = get_request_params(request).params
    request_params["limit"] = request.GET.dict().get("limit", EXPORT_DATASOURCE_DEFAULT_PAGINATION_LIMIT)
    if int(request_params["limit"]) > EXPORT_DATASOURCE_MAX_PAGINATION_LIMIT:
        request_params["limit"] = EXPORT_DATASOURCE_MAX_PAGINATION_LIMIT
    query = cursor_based_query_for_datasource(request_params, datasource_adapter)
    data = response_for_cursor_based_pagination(request, query, request_params, datasource_adapter)
    return JsonResponse(data)
