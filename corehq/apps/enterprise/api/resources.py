from dateutil import tz
from datetime import datetime
from tastypie import fields
from urllib.parse import urljoin
from django.http import HttpResponse
from django.template.loader import render_to_string
from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import ODataAuthentication
from corehq.apps.enterprise.enterprise import EnterpriseDomainReport
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.api.odata.views import add_odata_headers
from corehq.apps.api.odata.utils import FieldMetadata


class ODataResource(HqBaseResource):
    class Meta:
        include_resource_uri = False
        collection_name = 'value'
        authentication = ODataAuthentication()
        limit = 10
        max_limit = 20

    def alter_list_data_to_serialize(self, request, data):
        result = super().alter_list_data_to_serialize(request, data)

        meta = result['meta']
        result['@odata.count'] = meta['total_count']
        if 'next' in meta and meta['next']:
            result['@odata.nextLink'] = request.build_absolute_uri(meta['next'])

        del result['meta']
        return result

    def determine_format(self, request):
        # Currently a hack to force JSON. XML is supported by OData, but "Control Information" fields
        # (https://docs.oasis-open.org/odata/odata-json-format/v4.01/odata-json-format-v4.01.html#_Toc38457735)
        # are not valid attribute names in XML -- instead, they need to be implemented on the object's element.
        # https://docs.oasis-open.org/odata/odata-atom-format/v4.0/cs02/odata-atom-format-v4.0-cs02.html#_Entity
        # provides an example.
        # In the interrim, we forcing JSON to avoid XML is the best option
        return 'application/json'

    def create_response(self, request, data, response_class=HttpResponse, **response_kwargs):
        response = super().create_response(request, data, response_class, **response_kwargs)
        response['OData-Version'] = '4.0'
        return response

    def get_schema(self, request, **kwargs):
        """
        Returns a serialized form of the schema of the resource.

        Calls ``build_schema`` to generate the data. This method only responds
        to HTTP GET.

        Should return a HttpResponse (200 OK).
        """
        # ripped from Tastypie Resource's get_schema, only skipping building the bundle and using create_response
        self.method_check(request, allowed=['get'])
        self.is_authenticated(request)
        self.throttle_check(request)
        self.log_throttled_access(request)

        metadata = render_to_string('api/odata_metadata.xml', {
            'fields': self.get_fields(),
            'primary_key': self.get_primary_key(),
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
            fields.IntegerField: 'Edm.Int32'
        }

        for field_type, odata_type_name in mapping.items():
            if isinstance(field_object, field_type):
                return odata_type_name

        raise KeyError(type(field_object))

    def get_primary_key(self):
        raise NotImplementedError()


class DomainResource(ODataResource):
    domain = fields.CharField()
    created_on = fields.DateTimeField()
    num_apps = fields.IntegerField()
    num_mobile_users = fields.IntegerField()
    num_web_users = fields.IntegerField()
    num_sms_last_30_days = fields.IntegerField()
    last_form_submission = fields.DateTimeField()

    def get_object_list(self, request):
        account = BillingAccount.get_account_by_domain(request.domain)
        report = EnterpriseDomainReport(account, request.couch_user)
        return report.rows

    def obj_get_list(self, bundle, **kwargs):
        return self.get_object_list(bundle.request)

    def dehydrate(self, bundle):
        bundle.data['domain'] = bundle.obj[6]
        bundle.data['created_on'] = self.convert_date(bundle.obj[0])
        bundle.data['num_apps'] = bundle.obj[1]
        bundle.data['num_mobile_users'] = bundle.obj[2]
        bundle.data['num_web_users'] = bundle.obj[3]
        bundle.data['num_sms_last_30_days'] = bundle.obj[4]
        bundle.data['last_form_submission'] = self.convert_date(bundle.obj[5])

        return bundle

    @staticmethod
    def convert_date(date_string):
        # OData's edm:DateTimeOffset expects datetimes in ISO format: https://docs.oasis-open.org/odata/odata/v4.0/errata02/os/complete/part3-csdl/odata-v4.0-errata02-os-part3-csdl-complete.html#_Toc406398065  # noqa: E501
        if not date_string:
            return None

        time = datetime.strptime(date_string, '%Y/%m/%d %H:%M:%S')
        time = time.astimezone(tz.gettz('UTC'))
        return time.isoformat()

    def alter_list_data_to_serialize(self, request, data):
        result = super().alter_list_data_to_serialize(request, data)
        path = urljoin(request.get_full_path(), 'schema/#feed')
        result['@odata.context'] = request.build_absolute_uri(path)

        return result

    def get_primary_key(self):
        return 'domain'
