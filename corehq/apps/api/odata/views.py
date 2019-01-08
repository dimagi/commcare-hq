import os
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View

from corehq.apps.domain.decorators import api_auth
from corehq.util.view_utils import absolute_reverse


class ODataServiceView(View):

    @method_decorator(api_auth)
    def get(self, request, domain):
        data = {
            '@odata.context': absolute_reverse('odata_meta', args=[domain]),
            'value': [
                {
                    'name': 'Cases',
                    'kind': 'EntitySet',
                    'url': 'Cases',
                }
            ]
        }
        return add_odata_headers(JsonResponse(data))


class ODataMetadataView(View):

    @method_decorator(api_auth)
    def get(self, request, domain):
        # todo: should generate this dynamically based on the domain / case schema / data dictionary
        data_file = os.path.join(os.path.dirname(__file__), 'metadata.xml')
        with open(data_file, 'r') as f:
            return add_odata_headers(HttpResponse(f.read(), content_type='text/xml'))


def add_odata_headers(response):
    response['OData-Version'] = '4.0'
    return response
