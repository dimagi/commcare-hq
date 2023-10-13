import uuid

from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from memoized import memoized

from corehq import privileges, toggles
from corehq.apps.accounting.decorators import requires_privilege_with_fallback
from corehq.apps.api.decorators import allow_cors, api_throttle
from corehq.apps.domain.decorators import api_auth
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.users.decorators import require_permission
from corehq.apps.users.models import HqPermissions
from corehq.motech.generic_inbound.forms import (
    ApiValidationFormSet,
    ConfigurableAPICreateForm,
    ConfigurableAPIUpdateForm,
)
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    RequestLog,
)
from corehq.motech.generic_inbound.reports import ApiLogDetailView
from corehq.motech.generic_inbound.utils import (
    ApiRequest,
    archive_api_request,
    reprocess_api_request,
    log_api_request,
    process_api_request
)
from corehq.util import reverse
from corehq.util.view_utils import json_error


def can_administer_generic_inbound(view_fn):
    return toggles.GENERIC_INBOUND_API.required_decorator()(
        require_permission(HqPermissions.edit_motech)(view_fn)
    )


@method_decorator(can_administer_generic_inbound, name='dispatch')
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


@method_decorator(can_administer_generic_inbound, name='dispatch')
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
            return ConfigurableAPI.objects.get(domain=self.domain, id=self.api_id)
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
@api_auth(allow_creds_in_data=False)
@requires_privilege_with_fallback(privileges.API_ACCESS)
@require_permission(HqPermissions.edit_data)
@require_permission(HqPermissions.access_api)
@api_throttle
def generic_inbound_api(request, domain, api_id):
    try:
        api = ConfigurableAPI.objects.get(url_key=api_id, domain=domain)
    except ConfigurableAPI.DoesNotExist:
        raise Http404

    request_id = uuid.uuid4().hex

    def get_request_data():
        return ApiRequest.from_request(request, request_id=request_id)

    response = process_api_request(api, request_id, get_request_data)

    log_api_request(request_id, api, request, response)
    return response.get_http_response()


@can_administer_generic_inbound
def retry_api_request(request, domain, log_id):
    request_log = get_object_or_404(RequestLog, domain=domain, id=log_id)
    reprocess_api_request(request_log)
    return redirect(ApiLogDetailView.urlname, domain, log_id)


@can_administer_generic_inbound
def revert_api_request(request, domain, log_id):
    request_log = get_object_or_404(RequestLog, domain=domain, id=log_id)
    archive_api_request(request_log, request.couch_user._id)
    return redirect(ApiLogDetailView.urlname, domain, log_id)
