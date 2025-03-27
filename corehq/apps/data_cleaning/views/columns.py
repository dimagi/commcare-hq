from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.forms.columns import AddColumnForm
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class ManageColumnsFormView(BulkEditSessionViewMixin,
                            LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = "data_cleaning_manage_columns_form"
    template_name = "data_cleaning/forms/manage_columns_form.html"
    session_not_found_message = gettext_lazy("Cannot retrieve columns, session was not found.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'manage-columns',
            'active_columns': self.session.columns.all(),
            'add_column_form': kwargs.pop('column_form', None) or AddColumnForm(self.session),
        })
        return context

    @hq_hx_action('post')
    def add_column(self, request, *args, **kwargs):
        column_form = AddColumnForm(self.session, request.POST)
        if column_form.is_valid():
            column_form.add_column()
            column_form = None
        return self.get(request, column_form=column_form, *args, **kwargs)

    @hq_hx_action('post')
    def update_column_order(self, request, *args, **kwargs):
        # todo
        return self.get(request, *args, **kwargs)

    @hq_hx_action('post')
    def remove_column(self, request, *args, **kwargs):
        # todo
        return self.get(request, *args, **kwargs)
