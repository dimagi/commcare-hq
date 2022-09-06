from django.contrib import messages
from django.http import Http404
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from memoized import memoized
from psycopg2 import IntegrityError

from corehq import toggles
from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.motech.generic_inbound.forms import (
    ConfigurableAPICreateForm,
    ConfigurableAPIUpdateForm,
)
from corehq.motech.generic_inbound.models import ConfigurableAPI
from corehq.util import reverse


class ConfigurableAPIListView(BaseProjectSettingsView, CRUDPaginatedViewMixin):
    page_title = _("API Configurations")
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
            'slug': api.key,
            'url': api.absolute_url,
            'edit_url': reverse(ConfigurableAPIEditView.urlname, args=[self.domain, api.id]),
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return ConfigurableAPICreateForm(self.request, self.request.POST)
        return ConfigurableAPICreateForm(self.request)

    def get_create_item_data(self, create_form):
        try:
            new_expression = create_form.save()
        except IntegrityError:
            return {'error': _(f"API with name \"{create_form.cleaned_data['name']}\" already exists.")}
        return {
            "itemData": self._item_data(new_expression),
            "template": "base-api-config-template",
        }


@method_decorator(toggles.GENERIC_INBOUND_API.required_decorator(), name='dispatch')
class ConfigurableAPIEditView(BaseProjectSettingsView):
    page_title = _("Edit API Configuration")
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
        return self.get(request, domain, **kwargs)


def generic_inbound_api(request, domain, api_id):
    pass
