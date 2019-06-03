from __future__ import absolute_import, unicode_literals
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View

from corehq import toggles
from corehq.apps.api.odata.utils import get_case_type_to_properties
from corehq.apps.domain.decorators import basic_auth_or_try_api_key_auth
from corehq.apps.reports.analytics.esaccessors import get_case_types_for_domain_es
from corehq.util.view_utils import absolute_reverse


class ODataCaseServiceView(View):

    urlname = 'odata_case_service'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(toggles.ODATA.required_decorator())
    def get(self, request, domain):
        data = {
            '@odata.context': absolute_reverse(ODataCaseMetadataView.urlname, args=[domain]),
            'value': [
                {
                    'name': case_type,
                    'kind': 'EntitySet',
                    'url': case_type,
                }
                for case_type in get_case_types_for_domain_es(domain)
            ]
        }
        return add_odata_headers(JsonResponse(data))


class ODataCaseMetadataView(View):

    urlname = 'odata_case_meta'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(toggles.ODATA.required_decorator())
    def get(self, request, domain):
        case_type_to_properties = get_case_type_to_properties(domain)
        for case_type in case_type_to_properties:
            case_type_to_properties[case_type] = sorted(
                {'casename', 'casetype', 'dateopened', 'ownerid', 'backendid'}
                | set(case_type_to_properties[case_type])
            )
        metadata = render_to_string('api/odata_metadata.xml', {
            'case_type_to_properties': case_type_to_properties,
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


def add_odata_headers(response):
    response['OData-Version'] = '4.0'
    return response
