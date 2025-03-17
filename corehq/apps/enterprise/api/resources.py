from datetime import datetime, timezone
from urllib.parse import urljoin

from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from dateutil import tz
from tastypie import fields, http
from tastypie.exceptions import ImmediateHttpResponse

from corehq.apps.accounting.models import BillingAccount
from corehq.apps.accounting.utils.account import (
    get_account_or_404,
    request_has_permissions_for_enterprise_admin,
)
from corehq.apps.analytics.tasks import record_event
from corehq.apps.api.odata.utils import FieldMetadata
from corehq.apps.api.odata.views import add_odata_headers
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import ODataAuthentication
from corehq.apps.api.resources.meta import get_hq_throttle
from corehq.apps.api.keyset_paginator import KeysetPaginator
from corehq.apps.enterprise.enterprise import EnterpriseReport
from corehq.apps.enterprise.metric_events import ENTERPRISE_API_ACCESS
from corehq.apps.enterprise.iterators import IterableEnterpriseFormQuery, EnterpriseFormReportConverter

from corehq.apps.enterprise.tasks import generate_enterprise_report, ReportTaskProgress


class EnterpriseODataAuthentication(ODataAuthentication):
    def is_authenticated(self, request, **kwargs):
        authenticated = super().is_authenticated(request, **kwargs)
        if authenticated is not True:
            return authenticated

        domain = kwargs['domain'] if 'domain' in kwargs else request.domain
        account = get_account_or_404(domain)
        if not request_has_permissions_for_enterprise_admin(request, account):
            raise ImmediateHttpResponse(
                HttpResponseForbidden(_(
                    "You do not have permission to view this feed."
                ))
            )

        return True


class ODataResource(HqBaseResource):
    class Meta:
        include_resource_uri = False
        collection_name = 'value'
        authentication = ODataAuthentication()
        throttle = get_hq_throttle()
        limit = 2000
        max_limit = 10000

    def alter_list_data_to_serialize(self, request, data):
        result = super().alter_list_data_to_serialize(request, data)

        path = urljoin(request.get_full_path(), 'schema/#feed')
        result['@odata.context'] = request.build_absolute_uri(path)

        meta = result['meta']
        if 'total_count' in meta:
            result['@odata.count'] = meta['total_count']
        if 'next' in meta and meta['next']:
            result['@odata.nextLink'] = request.build_absolute_uri(meta['next'])

        del result['meta']
        return result

    def get_object_list(self, request):
        '''Intended to be overwritten in subclasses with query logic'''
        raise NotImplementedError()

    def obj_get_list(self, bundle, **kwargs):
        return self.get_object_list(bundle.request)

    def determine_format(self, request):
        # Currently a hack to force JSON. XML is supported by OData, but "Control Information" fields
        # (https://docs.oasis-open.org/odata/odata-json-format/v4.01/odata-json-format-v4.01.html#_Toc38457735)
        # are not valid attribute names in XML -- instead, they need to be implemented on the object's element.
        # https://docs.oasis-open.org/odata/odata-atom-format/v4.0/cs02/odata-atom-format-v4.0-cs02.html#_Entity
        # provides an example.
        # In the interrim, it seems forcing JSON to avoid XML is the best option
        return 'application/json'

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        response = super().create_response(request, data, response_class, **response_kwargs)
        response['OData-Version'] = '4.0'
        return response

    def get_schema(self, request, **kwargs):
        """
        Returns the OData Schema Representation of this resource, in XML.
        Only supports GET requests.
        """
        # ripped from Tastypie Resource's get_schema, only skipping building the bundle and using create_response
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)
        self.throttle_check(request)
        self.log_throttled_access(request)

        primary_keys = self.get_primary_keys()

        metadata = render_to_string('api/odata_metadata.xml', {
            'fields': self.get_fields(),
            'primary_keys': primary_keys,
        })

        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))

    def get_fields(self):
        result = []
        for field_name, field_object in self.fields.items():
            result.append(FieldMetadata(field_name, self.get_odata_class(field_object)))

        return result

    @staticmethod
    def get_odata_class(field_object):
        mapping = {
            fields.CharField: 'Edm.String',
            fields.DateTimeField: 'Edm.DateTimeOffset',
            fields.DateField: 'Edm.Date',
            fields.IntegerField: 'Edm.Int32'
        }

        for field_type, odata_type_name in mapping.items():
            if isinstance(field_object, field_type):
                return odata_type_name

        raise KeyError(type(field_object))

    def get_primary_keys(self):
        raise NotImplementedError()

    @classmethod
    def convert_datetime(cls, datetime_string):
        # OData's edm:DateTimeOffset expects datetimes in ISO format: https://docs.oasis-open.org/odata/odata/v4.0/errata02/os/complete/part3-csdl/odata-v4.0-errata02-os-part3-csdl-complete.html#_Toc406398065  # noqa: E501
        if not datetime_string:
            return None

        if isinstance(datetime_string, str):
            time = datetime.strptime(datetime_string, EnterpriseReport.DATE_ROW_FORMAT)
        else:
            time = datetime_string
        time = time.astimezone(tz.gettz('UTC'))
        return time.isoformat()


class ODataEnterpriseReportResource(ODataResource):
    REPORT_SLUG = None  # Override with correct slug
    # If this delay is too quick, clients like PowerBI
    # will hit their maximum number of retries before the report is ever generated.
    # If the delay is too long, then even reports that would generate in well under the retry
    # window will be subject to this delay (PowerBI will subject them to it twice,
    # as the data preview and actual request perform separate queries
    RETRY_IN_PROGRESS_DELAY = 60
    RETRY_CONFLICT_DELAY = 120

    COLUMN_MAP = {}  # Override with full mapping

    class Meta(ODataResource.Meta):
        authentication = EnterpriseODataAuthentication()

    def get_object_list(self, request):
        query_id = request.GET.get('query_id', None)
        progress = ReportTaskProgress(
            self.REPORT_SLUG, request.couch_user.username, query_id=query_id)
        status = progress.get_status()
        if status == ReportTaskProgress.STATUS_COMPLETE:
            # ensure this is for the same parameters
            if not progress.is_managing_task(self.get_report_task(request)):
                raise ImmediateHttpResponse(
                    response=http.HttpTooManyRequests(headers={'Retry-After': self.RETRY_CONFLICT_DELAY}))

            try:
                data = progress.get_data()
                progress.clear_status()  # Clear this request so that this user can issue new requests
            except KeyError:
                raise ImmediateHttpResponse(HttpResponseNotFound())

            # Because we are using a cacheable report, we need some way to tell tastypie to use
            # the generated report for future page requests.
            # By adding the report's query id to the request, the tastypie paginator will be able to
            # use it when generating 'next page' links
            # HACK: This is not ideal, as we are creeating a side effect within a 'get' method,
            # but it doesn't seem that Tastypie provides an alternate means of modifying links
            self._add_query_id_to_request(request, progress.get_query_id())
            return data
        elif status == ReportTaskProgress.STATUS_NEW:
            progress.start_task(self.get_report_task(request))
            record_event(ENTERPRISE_API_ACCESS, request.couch_user, {
                'api_type': self.REPORT_SLUG
            })

        # PowerBI respects delays with only two response codes:
        # 429 (TooManyRequests) and 503 (ServiceUnavailable). Although 503 is likely more semantically
        # correct here, 5XX errors are treated differently by our monitoring, and
        # PowerBI will only retry 503 requests 3 times, whereas 429s permit 6 retries
        raise ImmediateHttpResponse(
            response=http.HttpTooManyRequests(headers={'Retry-After': self.RETRY_IN_PROGRESS_DELAY}))

    def dehydrate(self, bundle):
        for (field_name, field) in self.fields.items():
            obj = bundle.obj[self.COLUMN_MAP[field_name]]
            if isinstance(field, fields.DateTimeField):
                obj = self.convert_datetime(obj)
            bundle.data[field_name] = obj

        return bundle

    def get_report_task(self, request):
        account = BillingAccount.get_account_by_domain(request.domain)
        return generate_enterprise_report.s(
            self.REPORT_SLUG,
            account.id,
            request.couch_user.username,
        )

    def _add_query_id_to_request(self, request, query_id):
        if 'report' not in request.GET:
            new_params = request.GET.copy()
            new_params['query_id'] = query_id
            request.GET = new_params


class DomainResource(ODataEnterpriseReportResource):
    domain = fields.CharField()
    created_on = fields.DateTimeField()
    num_apps = fields.IntegerField()
    num_mobile_users = fields.IntegerField()
    num_web_users = fields.IntegerField()
    num_sms_last_30_days = fields.IntegerField()
    last_form_submission = fields.DateTimeField()
    num_odata_feeds_used = fields.IntegerField(null=True)
    num_odata_feeds_available = fields.IntegerField(null=True)

    REPORT_SLUG = EnterpriseReport.DOMAINS

    COLUMN_MAP = {
        'domain': 8,
        'created_on': 0,
        'num_apps': 1,
        'num_mobile_users': 2,
        'num_web_users': 3,
        'num_sms_last_30_days': 4,
        'last_form_submission': 5,
        'num_odata_feeds_used': 6,
        'num_odata_feeds_available': 7,
    }

    def get_primary_keys(self):
        return ('domain',)


class WebUserResource(ODataEnterpriseReportResource):
    email = fields.CharField()
    name = fields.CharField()
    role = fields.CharField()
    last_login = fields.DateTimeField(null=True)
    last_access_date = fields.DateField(null=True)
    status = fields.CharField()
    domain = fields.CharField()

    REPORT_SLUG = EnterpriseReport.WEB_USERS

    COLUMN_MAP = {
        'email': 0,
        'name': 1,
        'role': 2,
        'last_login': 3,
        'last_access_date': 4,
        'status': 5,
        'domain': 6,
    }

    def dehydrate(self, bundle):
        bundle.obj[self.COLUMN_MAP['last_login']] = \
            self.convert_not_available(bundle.obj[self.COLUMN_MAP['last_login']])
        bundle.obj[self.COLUMN_MAP['last_access_date']] = \
            self.convert_not_available(bundle.obj[self.COLUMN_MAP['last_access_date']])
        bundle = super().dehydrate(bundle)
        bundle.data['name'] = self.convert_not_available(bundle.data['name'])

        return bundle

    @classmethod
    def convert_not_available(cls, value):
        return None if value == 'N/A' else value

    def get_primary_keys(self):
        return ('email',)


class MobileUserResource(ODataEnterpriseReportResource):
    username = fields.CharField()
    name = fields.CharField()
    email = fields.CharField()
    role = fields.CharField()
    created_at = fields.DateTimeField()
    last_sync = fields.DateTimeField()
    last_submission = fields.DateTimeField()
    commcare_version = fields.CharField(blank=True)
    user_id = fields.CharField()
    domain = fields.CharField()

    REPORT_SLUG = EnterpriseReport.MOBILE_USERS

    COLUMN_MAP = {
        'username': 0,
        'name': 1,
        'email': 2,
        'role': 3,
        'created_at': 4,
        'last_sync': 5,
        'last_submission': 6,
        'commcare_version': 7,
        'user_id': 8,
        'domain': 9,
    }

    def get_primary_keys(self):
        return ('user_id',)


class SMSResource(ODataEnterpriseReportResource):
    domain = fields.CharField()
    num_sent = fields.IntegerField()
    num_received = fields.IntegerField()
    num_error = fields.IntegerField()

    REPORT_SLUG = EnterpriseReport.SMS

    COLUMN_MAP = {
        'domain': 0,
        'num_sent': 1,
        'num_received': 2,
        'num_error': 3,
    }

    def get_report_task(self, request):
        start_date, end_date = get_date_range_from_request(request.GET)

        account = BillingAccount.get_account_by_domain(request.domain)
        return generate_enterprise_report.s(
            self.REPORT_SLUG,
            account.id,
            request.couch_user.username,
            start_date=start_date,
            end_date=end_date
        )

    def get_primary_keys(self):
        return ('domain',)


def get_date_range_from_request(request_dict):
    start_date = request_dict.get('startdate', None)
    if start_date:
        start_date = str(datetime.fromisoformat(start_date).astimezone(timezone.utc))

    end_date = request_dict.get('enddate', None)
    if end_date:
        end_date = str(datetime.fromisoformat(end_date).astimezone(timezone.utc))

    return (start_date, end_date,)


class ODataFeedResource(ODataEnterpriseReportResource):
    '''
    A Resource for listing all Domain-level OData feeds which belong to the Enterprise.
    Currently includes summary rows as well as individual reports
    '''

    domain = fields.CharField()
    report_name = fields.CharField()
    report_rows = fields.IntegerField()

    REPORT_SLUG = EnterpriseReport.ODATA_FEEDS

    COLUMN_MAP = {
        'domain': 0,
        'report_name': 1,
        'report_rows': 2,
    }

    def get_primary_keys(self):
        return ('domain', 'report_name',)


class FormSubmissionResource(ODataEnterpriseReportResource):
    class Meta(ODataEnterpriseReportResource.Meta):
        paginator_class = KeysetPaginator
        limit = 10000
        max_limit = 20000

    form_id = fields.CharField()
    form_name = fields.CharField()
    submitted = fields.DateTimeField()
    app_name = fields.CharField()
    username = fields.CharField()
    domain = fields.CharField()

    REPORT_SLUG = EnterpriseReport.FORM_SUBMISSIONS

    # Because FormSubmissionResource retrieves its data from an IterableEnterpriseFormQuery rather than
    # an enterprise report, the columns are referenced by string rather than index
    COLUMN_MAP = {
        'form_id': 'form_id',
        'form_name': 'form_name',
        'submitted': 'submitted',
        'app_name': 'app_name',
        'username': 'username',
        'domain': 'domain'
    }

    def get_object_list(self, request):
        start_date = request.GET.get('startdate', None)
        if start_date:
            start_date = datetime.fromisoformat(start_date).astimezone(timezone.utc)

        end_date = request.GET.get('enddate', None)
        if end_date:
            end_date = datetime.fromisoformat(end_date).astimezone(timezone.utc)

        account = BillingAccount.get_account_by_domain(request.domain)

        converter = EnterpriseFormReportConverter()
        query_kwargs = converter.get_kwargs_from_map(request.GET)
        if converter.is_initial_query(request.GET):
            record_event(ENTERPRISE_API_ACCESS, request.couch_user, {
                'api_type': self.REPORT_SLUG
            })

        return IterableEnterpriseFormQuery(account, converter, start_date, end_date, **query_kwargs)

    def get_primary_keys(self):
        return ('form_id', 'submitted',)


class CaseManagementResource(ODataEnterpriseReportResource):
    domain = fields.CharField()
    num_applications = fields.IntegerField()
    num_surveys_only = fields.IntegerField()
    num_cases_only = fields.IntegerField()
    num_mixed = fields.IntegerField()

    REPORT_SLUG = EnterpriseReport.CASE_MANAGEMENT

    COLUMN_MAP = {
        'domain': 0,
        'num_applications': 1,
        'num_surveys_only': 2,
        'num_cases_only': 3,
        'num_mixed': 4,
    }

    def get_primary_keys(self):
        return ('domain',)


class DataExportReportResource(ODataEnterpriseReportResource):
    domain = fields.CharField()
    name = fields.CharField()
    export_type = fields.CharField()
    export_subtype = fields.CharField()
    owner = fields.CharField()

    REPORT_SLUG = EnterpriseReport.DATA_EXPORTS

    COLUMN_MAP = {
        'domain': 0,
        'name': 1,
        'export_type': 2,
        'export_subtype': 3,
        'owner': 4,
    }

    def get_primary_keys(self):
        return ('domain', 'export_type', 'export_subtype', 'name')


class TwoFactorAuthResource(ODataEnterpriseReportResource):
    domain_without_2fa = fields.CharField()

    REPORT_SLUG = EnterpriseReport.TWO_FACTOR_AUTH

    COLUMN_MAP = {
        'domain_without_2fa': 0,
    }

    def get_primary_keys(self):
        return ('domain_without_2fa',)


class CommCareVersionComplianceResource(ODataEnterpriseReportResource):
    mobile_worker = fields.CharField()
    domain = fields.CharField()
    latest_version_available_at_submission = fields.CharField()
    version_in_use = fields.CharField()

    REPORT_SLUG = EnterpriseReport.COMMCARE_VERSION_COMPLIANCE

    COLUMN_MAP = {
        'mobile_worker': 0,
        'domain': 1,
        'latest_version_available_at_submission': 2,
        'version_in_use': 3,
    }

    def get_primary_keys(self):
        return ('mobile_worker', 'domain',)


class APIKeysResource(ODataEnterpriseReportResource):
    web_user = fields.CharField()
    api_key_name = fields.CharField()
    scope = fields.CharField()
    expiration_date = fields.DateTimeField()
    created_date = fields.DateTimeField()
    last_used_date = fields.DateTimeField()

    REPORT_SLUG = EnterpriseReport.API_KEYS

    COLUMN_MAP = {
        'web_user': 0,
        'api_key_name': 1,
        'scope': 2,
        'expiration_date': 3,
        'created_date': 4,
        'last_used_date': 5,
    }

    def get_primary_keys(self):
        return ('web_user', 'api_key_name',)


class DataForwardingResource(ODataEnterpriseReportResource):
    domain = fields.CharField()
    service_name = fields.CharField()
    service_type = fields.CharField()
    last_modified = fields.DateTimeField()

    REPORT_SLUG = EnterpriseReport.DATA_FORWARDING

    COLUMN_MAP = {
        'domain': 0,
        'service_name': 1,
        'service_type': 2,
        'last_modified': 3,
    }

    def get_primary_keys(self):
        return ('domain', 'service_name', 'service_type')


class ApplicationVersionComplianceResource(ODataEnterpriseReportResource):
    mobile_worker = fields.CharField()
    domain = fields.CharField()
    application = fields.CharField()
    latest_version_available_when_last_used = fields.CharField()
    version_in_use = fields.CharField()
    last_used = fields.DateTimeField()

    REPORT_SLUG = EnterpriseReport.APP_VERSION_COMPLIANCE

    COLUMN_MAP = {
        'mobile_worker': 0,
        'domain': 1,
        'application': 2,
        'latest_version_available_when_last_used': 3,
        'version_in_use': 4,
        'last_used': 5,
    }

    def get_primary_keys(self):
        return ('mobile_worker', 'application',)
