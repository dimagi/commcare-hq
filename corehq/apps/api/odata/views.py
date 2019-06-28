from __future__ import absolute_import, unicode_literals

from collections import OrderedDict

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View

from corehq import toggles
from corehq.apps.api.odata.utils import (
    get_case_odata_fields_from_config,
    get_case_type_to_properties,
    get_xmlns_by_app,
    get_xmlns_to_properties,
)
from corehq.apps.domain.decorators import basic_auth_or_try_api_key_auth
from corehq.apps.export.dbaccessors import get_odata_case_configs_by_domain
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
                {'case_name', 'case_type', 'date_opened', 'owner_id', 'backend_id'}
                | set(case_type_to_properties[case_type])
            )
        metadata = render_to_string('api/odata_metadata.xml', {
            'case_type_to_properties': case_type_to_properties,
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


class ODataFormServiceView(View):

    urlname = 'odata_form_service'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(toggles.ODATA.required_decorator())
    def get(self, request, domain, app_id):
        data = {
            '@odata.context': absolute_reverse(ODataFormMetadataView.urlname, args=[domain, app_id]),
            'value': [
                {
                    'name': xmlns,
                    'kind': 'EntitySet',
                    'url': xmlns,
                }
                for xmlns in get_xmlns_by_app(domain, app_id)
            ]
        }
        return add_odata_headers(JsonResponse(data))


class ODataFormMetadataView(View):

    urlname = 'odata_form_meta'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(toggles.ODATA.required_decorator())
    def get(self, request, domain, app_id):
        xmlns_to_properties = get_xmlns_to_properties(domain, app_id)
        metadata = render_to_string('api/odata_form_metadata.xml', {
            'xmlns_to_properties': xmlns_to_properties,
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


class ODataCaseServiceFromExportInstanceView(View):

    urlname = 'odata_case_service_from_export_instance'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(toggles.ODATA.required_decorator())
    def get(self, request, domain):
        service_document_content = {
            '@odata.context': absolute_reverse(ODataCaseMetadataFromExportInstanceView.urlname, args=[domain]),
            'value': [
                {
                    'name': config.get_id,
                    'kind': 'EntitySet',
                    'url': config.get_id,
                }
                for config in get_odata_case_configs_by_domain(domain)
            ]
        }
        return add_odata_headers(JsonResponse(service_document_content))


class ODataCaseMetadataFromExportInstanceView(View):

    urlname = 'odata_case_metadata_from_export_instance'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(toggles.ODATA.required_decorator())
    def get(self, request, domain):
        configs = get_odata_case_configs_by_domain(domain)
        config_ids_to_properties = OrderedDict()
        for config in sorted(configs, key=lambda _config: _config.get_id):  # For deterministic tests
            config_ids_to_properties[config.get_id] = get_case_odata_fields_from_config(config)
        metadata = render_to_string('api/case_odata_metadata.xml', {
            'config_ids_to_properties': config_ids_to_properties,
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


def add_odata_headers(response):
    response['OData-Version'] = '4.0'
    return response
