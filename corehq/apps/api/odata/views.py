from __future__ import absolute_import, unicode_literals

from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View

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

odata_auth = method_decorator([
    basic_auth_or_try_api_key_auth,
    require_permission(Permissions.edit_data, login_decorator=None),
    BI_INTEGRATION_PREVIEW.required_decorator(),
], name='dispatch')


@odata_auth
class ODataCaseServiceView(View):

    urlname = 'odata_case_service_from_export_instance'
    table_urlname = 'odata_case_service_from_export_instance_table'

    def get(self, request, domain, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        urlname = ODataCaseMetadataView.urlname
        url_args = [domain, config_id]
        if table_id > 0:
            urlname = ODataCaseMetadataView.table_urlname
            url_args.append(table_id)
        service_document_content = {
            '@odata.context': absolute_reverse(urlname, args=url_args),
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }]
        }
        return add_odata_headers(JsonResponse(service_document_content))


@odata_auth
class ODataCaseMetadataView(View):

    urlname = 'odata_case_metadata_from_export_instance'
    table_urlname = 'odata_case_metadata_from_export_instance_table'

    def get(self, request, domain, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        config = get_document_or_404(CaseExportInstance, domain, config_id)
        metadata = render_to_string('api/odata_metadata.xml', {
            'fields': get_case_odata_fields_from_config(config, table_id),
            'primary_key': 'caseid' if table_id == 0 else 'number',
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


@odata_auth
class ODataFormServiceView(View):

    urlname = 'odata_form_service_from_export_instance'
    table_urlname = 'odata_form_service_from_export_instance_table'

    def get(self, request, domain, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        urlname = ODataFormMetadataView.urlname
        url_args = [domain, config_id]
        if table_id > 0:
            urlname = ODataFormMetadataView.table_urlname
            url_args.append(table_id)
        service_document_content = {
            '@odata.context': absolute_reverse(urlname, args=url_args),
            'value': [{
                'name': 'feed',
                'kind': 'EntitySet',
                'url': 'feed',
            }]
        }
        return add_odata_headers(JsonResponse(service_document_content))


@odata_auth
class ODataFormMetadataView(View):

    urlname = 'odata_form_metadata_from_export_instance'
    table_urlname = 'odata_form_metadata_from_export_instance_table'

    def get(self, request, domain, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        config = get_document_or_404(FormExportInstance, domain, config_id)
        metadata = render_to_string('api/odata_metadata.xml', {
            'fields': get_form_odata_fields_from_config(config, table_id),
            'primary_key': 'formid' if table_id == 0 else 'number',
        })
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


def add_odata_headers(response):
    response['OData-Version'] = '4.0'
    return response
