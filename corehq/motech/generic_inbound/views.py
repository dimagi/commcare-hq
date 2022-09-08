from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_http_methods
from memoized import memoized

from corehq import toggles
from corehq.apps.api.decorators import api_throttle
from corehq.apps.domain.decorators import api_auth
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqcase.api.core import UserError, SubmissionError, serialize_case
from corehq.apps.hqcase.api.updates import handle_case_update
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.motech.generic_inbound.exceptions import GenericInboundUserError
from corehq.motech.generic_inbound.forms import (
    ConfigurableAPICreateForm,
    ConfigurableAPIUpdateForm,
)
from corehq.motech.generic_inbound.models import ConfigurableAPI
from corehq.motech.generic_inbound.utils import get_context_from_request
from corehq.util import reverse
from corehq.util.view_utils import json_error


class ConfigurableAPIListView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    page_title = gettext_lazy("API Configurations")
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

        main_context.update({
            "form": self.get_form(),
            "api_model": self.api,
        })
        return main_context

    def post(self, request, domain, **kwargs):
        form = self.get_form()
        if form.is_valid():
            form.save()
            messages.success(request, _("API Configuration updated successfully."))
        return redirect(self.page_url, domain, self.api_id)


@json_error
@api_auth
@api_throttle
@require_http_methods(["POST"])
def generic_inbound_api(request, domain, api_id):
    try:
        api = ConfigurableAPI.objects.get(url_key=api_id, domain=domain)
    except ConfigurableAPI.DoesNotExist:
        raise Http404

    try:
        context = get_context_from_request(request)
    except GenericInboundUserError as e:
        return JsonResponse({'error': str(e)}, status=400)

    try:
        response = _execute_case_api(
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
    except SubmissionError as e:
        return JsonResponse({
            'error': str(e),
            'form_id': e.form_id,
        }, status=400)

    return JsonResponse(response)


def _execute_case_api(domain, couch_user, device_id, context, api_model):
    data = api_model.parsed_expression(context.root_doc, context)

    if not isinstance(data, list):
        # the bulk API always requires a list
        data = [data]

    xform, case_or_cases = handle_case_update(
        domain=domain,
        data=data,
        user=couch_user,
        device_id=device_id,
        is_creation=None,
    )

    if isinstance(case_or_cases, list):
        return {
            'form_id': xform.form_id,
            'cases': [serialize_case(case) for case in case_or_cases],
        }
    return {
        'form_id': xform.form_id,
        'case': serialize_case(case_or_cases),
    }
