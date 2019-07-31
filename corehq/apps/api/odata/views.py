from __future__ import absolute_import, unicode_literals

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View

from corehq import toggles
from corehq.apps.api.odata.utils import (
    get_case_odata_fields_from_config,
    get_form_odata_fields_from_config,
)
from corehq.apps.domain.decorators import basic_auth_or_try_api_key_auth
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import Permissions
from corehq.feature_previews import BI_INTEGRATION_PREVIEW
from corehq.util import get_document_or_404
from corehq.util.view_utils import absolute_reverse


class ODataCaseServiceView(View):

    urlname = 'odata_case_service_from_export_instance'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(require_permission(Permissions.edit_data, login_decorator=None))
    @method_decorator(BI_INTEGRATION_PREVIEW.required_decorator())
    def get(self, request, domain, config_id):
        service_document_content = {
            '@odata.context': absolute_reverse(ODataCaseMetadataView.urlname, args=[domain, config_id]),
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }]
        }
        return add_odata_headers(JsonResponse(service_document_content))


class ODataCaseMetadataView(View):

    urlname = 'odata_case_metadata_from_export_instance'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(require_permission(Permissions.edit_data, login_decorator=None))
    @method_decorator(BI_INTEGRATION_PREVIEW.required_decorator())
    def get(self, request, domain, config_id):
        config = get_document_or_404(CaseExportInstance, domain, config_id)
        metadata = render_to_string('api/case_odata_metadata.xml', {
            'fields': get_case_odata_fields_from_config(config),
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


class ODataFormServiceView(View):

    urlname = 'odata_form_service_from_export_instance'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(require_permission(Permissions.edit_data, login_decorator=None))
    @method_decorator(BI_INTEGRATION_PREVIEW.required_decorator())
    def get(self, request, domain, config_id):
        service_document_content = {
            '@odata.context': absolute_reverse(ODataFormMetadataView.urlname, args=[domain, config_id]),
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }]
        }
        return add_odata_headers(JsonResponse(service_document_content))


class ODataFormMetadataView(View):

    urlname = 'odata_form_metadata_from_export_instance'

    @method_decorator(basic_auth_or_try_api_key_auth)
    @method_decorator(require_permission(Permissions.edit_data, login_decorator=None))
    @method_decorator(BI_INTEGRATION_PREVIEW.required_decorator())
    def get(self, request, domain, config_id):
        config = get_document_or_404(FormExportInstance, domain, config_id)
        metadata = render_to_string('api/form_odata_metadata.xml', {
            'fields': get_form_odata_fields_from_config(config),
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


def add_odata_headers(response):
    response['OData-Version'] = '4.0'
    return response
