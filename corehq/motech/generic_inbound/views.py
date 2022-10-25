import json

from django.contrib import messages
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from memoized import memoized

from dimagi.utils.web import get_ip

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors, api_throttle
from corehq.apps.auditcare.models import get_standard_headers
from corehq.apps.domain.decorators import api_auth
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqcase.api.core import SubmissionError, UserError
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.motech.generic_inbound.core import execute_generic_api
from corehq.motech.generic_inbound.exceptions import (
    GenericInboundRequestFiltered,
    GenericInboundUserError,
    GenericInboundValidationError,
)
from corehq.motech.generic_inbound.forms import (
    ApiValidationFormSet,
    ConfigurableAPICreateForm,
    ConfigurableAPIUpdateForm,
)
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    ProcessingAttempt,
    RequestLog,
)
from corehq.motech.generic_inbound.utils import get_context_from_request
from corehq.util import reverse
from corehq.util.view_utils import json_error


@method_decorator(toggles.GENERIC_INBOUND_API.required_decorator(), name='dispatch')
class ConfigurableAPIListView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    page_title = gettext_lazy("Inbound API Configurations")
    urlname = "configurable_api_list"
    template_name = "generic_inbound/api_list.html"
    create_item_form_class = "form form-horizontal"

    @property
    def base_query(self):
        return ConfigurableAPI.objects.filter(domain=self.domain)

    @property
    def total(self):
        return self.base_query.count()

    def post(self, *args, **kwargs):
        return self.paginate_crud_response

    @property
    def column_names(self):
        return [
            _("Name"),
            _("Description"),
            _("URL"),
            _("Actions"),
        ]

    @property
    def page_context(self):
        return self.pagination_context

    @property
    def paginated_list(self):
        for api in self.base_query.all():
            yield {
                "itemData": self._item_data(api),
                "template": "base-api-config-template",
            }

    def _item_data(self, api):
        return {
            'id': api.id,
            'name': api.name,
            'description': api.description,
            'api_url': api.absolute_url,
            'edit_url': reverse(ConfigurableAPIEditView.urlname, args=[self.domain, api.id]),
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return ConfigurableAPICreateForm(self.request, self.request.POST)
        return ConfigurableAPICreateForm(self.request)

    def get_create_item_data(self, create_form):
        new_api = create_form.save()
        return {
            "itemData": self._item_data(new_api),
            "template": "base-api-config-template",
        }


@method_decorator(toggles.GENERIC_INBOUND_API.required_decorator(), name='dispatch')
class ConfigurableAPIEditView(BaseProjectSettingsView):
    page_title = gettext_lazy("Edit API Configuration")
    urlname = "configurable_api_edit"
    template_name = "generic_inbound/api_edit.html"

    @property
    def api_id(self):
        return self.kwargs['api_id']

    @property
    @memoized
    def api(self):
        try:
            return ConfigurableAPI.objects.get(id=self.api_id)
        except ConfigurableAPI.DoesNotExist:
            raise Http404

    @property
    def page_url(self):
        return reverse(self.urlname, args=(self.domain, self.api_id,))

    def get_form(self):
        if self.request.method == 'POST':
            return ConfigurableAPIUpdateForm(self.request, self.request.POST, instance=self.api)
        return ConfigurableAPIUpdateForm(self.request, instance=self.api)

    @property
    def main_context(self):
        main_context = super(ConfigurableAPIEditView, self).main_context

        filter_expressions = [
            {"id": expr.id, "label": str(expr)}
            for expr in UCRExpression.objects.get_filters_for_domain(self.domain)
        ]
        main_context.update({
            "form": self.get_form(),
            "api_model": self.api,
            "filter_expressions": filter_expressions,
            "validations": [
                validation.to_json()
                for validation in self.api.validations.all()
            ],
            "page_title": self.page_title
        })
        return main_context

    def post(self, request, domain, **kwargs):
        form = self.get_form()
        validation_formset = ApiValidationFormSet(self.request.POST, instance=self.api)
        if form.is_valid() and validation_formset.is_valid():
            form.save()
            validation_formset.save()
            messages.success(request, _("API Configuration updated successfully."))
            return redirect(self.urlname, self.domain, self.api_id)

        if not validation_formset.is_valid():
            messages.error(request, _("There is an error in your data API validations"))
        return self.get(request, self.domain, **kwargs)


@json_error
@csrf_exempt
@allow_cors(list(RequestLog.RequestMethod))
@require_http_methods(list(RequestLog.RequestMethod))
@api_auth
@requires_privilege_with_fallback(privileges.API_ACCESS)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@api_throttle
def generic_inbound_api(request, domain, api_id):
    try:
        api = ConfigurableAPI.objects.get(url_key=api_id, domain=domain)
    except ConfigurableAPI.DoesNotExist:
        raise Http404

    response = _generic_inbound_api(api, request)
    _log_api_request(api, request, response)
    return response


def _generic_inbound_api(api, request):
    try:
        context = get_context_from_request(request)
    except GenericInboundUserError as e:
        return JsonResponse({'error': str(e)}, status=400)

    try:
        response = execute_generic_api(
            request.domain,
            request.couch_user,
            request.META.get('HTTP_USER_AGENT'),
            context,
            api
        )
    except BadSpecError as e:
        return JsonResponse({'error': str(e)}, status=500)
    except UserError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except GenericInboundRequestFiltered:
        return HttpResponse(status=204)  # no body for 204 (RFC 7230)
    except GenericInboundValidationError as e:
        return _get_validation_error_response(e.errors)
    except SubmissionError as e:
        return JsonResponse({
            'error': str(e),
            'form_id': e.form_id,
        }, status=400)

    return JsonResponse(response)


def _get_validation_error_response(errors):
    return JsonResponse({'error': 'validation error', 'errors': [
        error['message'] for error in errors
    ]}, status=400)


def _log_api_request(api, request, response):
    if response.status_code == 200:
        is_success = True
        status = RequestLog.Status.SUCCESS
    elif response.status_code == 204:
        is_success = True
        status = RequestLog.Status.FILTERED
    elif response.status_code == 400:
        is_success = False
        status = RequestLog.Status.VALIDATION_FAILED
    else:
        is_success = False
        status = RequestLog.Status.ERROR

    response_body = response.content.decode('utf-8')
    log = RequestLog.objects.create(
        domain=request.domain,
        api=api,
        status=status,
        response_status=response.status_code,
        error_message=response_body if not is_success else '',
        username=request.couch_user.username,
        request_method=request.method,
        request_query=request.META.get('QUERY_STRING'),
        request_body=request.body.decode('utf-8'),
        request_headers=get_standard_headers(request.META),
        request_ip=get_ip(request),
    )

    response_json = json.loads(response.content)
    if is_success:
        case_ids = [c['case_id'] for c in
                    response_json.get('cases', [response_json.get('case')])]
    else:
        case_ids = []
    ProcessingAttempt.objects.create(
        log=log,
        response_status=response.status_code,
        response_body=response_body,
        raw_response=response_json,
        xform_id=response_json.get('form_id'),
        case_ids=case_ids,
    )
