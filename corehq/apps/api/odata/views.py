from django.http import HttpResponse, JsonResponse, Http404
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View

from corehq.apps.analytics.utils.partner_analytics import (
    track_partner_access,
    ACCESS_ODATA,
)
from corehq.apps.api.odata.utils import (
    get_case_odata_fields_from_config,
    get_form_odata_fields_from_config,
)
from corehq.apps.domain.decorators import basic_auth_or_try_api_key_auth
from corehq.apps.export.const import FORM_EXPORT
from corehq.apps.export.models import CaseExportInstance, FormExportInstance
from corehq.apps.export.views.utils import (
    user_can_view_odata_feed,
    user_can_view_deid_exports,
)
from corehq.apps.locations.permissions import location_safe
from corehq.apps.users.decorators import require_permission_raw
from corehq.apps.users.permissions import (
    FORM_EXPORT_PERMISSION,
    CASE_EXPORT_PERMISSION,
    has_permission_to_view_report,
)
from corehq.util import get_document_or_404
from corehq.util.view_utils import absolute_reverse


def odata_permissions_check(user, domain):
    return user_can_view_odata_feed(domain, user)


odata_auth = method_decorator([
    require_permission_raw(
        odata_permissions_check,
        basic_auth_or_try_api_key_auth
    ),
], name='dispatch')


def raise_odata_permissions_issues(user, domain, config):
    if config.is_deidentified:
        return not (
            user_can_view_deid_exports(domain, user)
            and user_can_view_odata_feed(domain, user)
        )
    return not (
        has_permission_to_view_report(
            user,
            domain,
            FORM_EXPORT_PERMISSION if config.type == FORM_EXPORT else CASE_EXPORT_PERMISSION
        ) and user_can_view_odata_feed(domain, user)
    )


class BaseODataView(View):

    def dispatch(self, request, *args, **kwargs):
        if not user_can_view_odata_feed(request.domain, request.couch_user):
            raise Http404()
        return super(BaseODataView, self).dispatch(request, *args, **kwargs)


@location_safe
@odata_auth
class ODataCaseServiceView(BaseODataView):

    urlname = 'odata_case_service_from_export_instance'
    table_urlname = 'odata_case_service_from_export_instance_table'

    def get(self, request, domain, api_version, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        config = get_document_or_404(CaseExportInstance, domain, config_id)
        if raise_odata_permissions_issues(request.couch_user, domain, config):
            raise Http404()
        urlname = ODataCaseMetadataView.urlname
        url_args = [domain, api_version, config_id]
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


@location_safe
@odata_auth
class ODataCaseMetadataView(BaseODataView):

    urlname = 'odata_case_metadata_from_export_instance'
    table_urlname = 'odata_case_metadata_from_export_instance_table'

    def get(self, request, domain, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        config = get_document_or_404(CaseExportInstance, domain, config_id)
        if raise_odata_permissions_issues(request.couch_user, domain, config):
            raise Http404()
        case_fields = get_case_odata_fields_from_config(config, table_id)

        field_names = [f.name for f in case_fields]
        primary_key = 'caseid' if table_id == 0 else 'number'
        if f'{primary_key} *sensitive*' in field_names:
            primary_key = f'{primary_key} *sensitive*'

        metadata = render_to_string('api/odata_metadata.xml', {
            'fields': case_fields,
            'primary_keys': (primary_key,),
        })
        track_partner_access(ACCESS_ODATA, domain)
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


@location_safe
@odata_auth
class ODataFormServiceView(BaseODataView):

    urlname = 'odata_form_service_from_export_instance'
    table_urlname = 'odata_form_service_from_export_instance_table'

    def get(self, request, domain, api_version, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        config = get_document_or_404(FormExportInstance, domain, config_id)
        if raise_odata_permissions_issues(request.couch_user, domain, config):
            raise Http404()
        urlname = ODataFormMetadataView.urlname
        url_args = [domain, api_version, config_id]
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


@location_safe
@odata_auth
class ODataFormMetadataView(BaseODataView):

    urlname = 'odata_form_metadata_from_export_instance'
    table_urlname = 'odata_form_metadata_from_export_instance_table'

    def get(self, request, domain, config_id, **kwargs):
        table_id = int(kwargs.get('table_id', 0))
        config = get_document_or_404(FormExportInstance, domain, config_id)
        if raise_odata_permissions_issues(request.couch_user, domain, config):
            raise Http404()
        form_fields = get_form_odata_fields_from_config(config, table_id)

        field_names = [f.name for f in form_fields]
        primary_key = 'formid' if table_id == 0 else 'number'
        if f'{primary_key} *sensitive*' in field_names:
            primary_key = f'{primary_key} *sensitive*'

        metadata = render_to_string('api/odata_metadata.xml', {
            'fields': form_fields,
            'primary_keys': (primary_key,),
        })
        track_partner_access(ACCESS_ODATA, domain)
        return add_odata_headers(HttpResponse(metadata, content_type='application/xml'))


def add_odata_headers(response):
    response['OData-Version'] = '4.0'
    return response
