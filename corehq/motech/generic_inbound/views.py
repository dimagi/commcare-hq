from django.utils.translation import gettext as _
from psycopg2 import IntegrityError

from corehq.apps.domain.views import BaseProjectSettingsView
from corehq.apps.hqwebapp.views import CRUDPaginatedViewMixin
from corehq.motech.generic_inbound.forms import ConfigurableAPIForm
from corehq.motech.generic_inbound.models import ConfigurableAPI


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
        }

    def get_create_form(self, is_blank=False):
        if self.request.method == 'POST' and not is_blank:
            return ConfigurableAPIForm(self.request, self.request.POST)
        return ConfigurableAPIForm(self.request)

    def get_create_item_data(self, create_form):
        try:
            new_expression = create_form.save()
        except IntegrityError:
            return {'error': _(f"API with name \"{create_form.cleaned_data['name']}\" already exists.")}
        return {
            "itemData": self._item_data(new_expression),
            "template": "base-api-config-template",
        }
