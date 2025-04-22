from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.forms.cleaning import CleanSelectedRecordsForm
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator([
    use_bootstrap5,
    require_bulk_data_cleaning_cases,
], name='dispatch')
class CleanSelectedRecordsFormView(BulkEditSessionViewMixin,
                                   LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView):
    urlname = "data_cleaning_clean_selected_records_form"
    template_name = "data_cleaning/forms/clean_selected_records_form.html"
    session_not_found_message = gettext_lazy("Cannot load clean selected records form, session was not found.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'container_id': 'clean-selected-records',
            'cleaning_form': kwargs.pop('cleaning_form', None) or CleanSelectedRecordsForm(self.session),
            'change': kwargs.pop('change', None),
        })
        return context

    @hq_hx_action('post')
    def create_bulk_edit_change(self, request, *args, **kwargs):
        cleaning_form = CleanSelectedRecordsForm(self.session, request.POST)
        change = None
        if cleaning_form.is_valid():
            from django.conf import settings

            # temporarily disallow QA to accidentally create bulk edit changes
            # that they cannot see
            if settings.SERVER_ENVIRONMENT == settings.LOCAL_SERVER_ENVIRONMENT:
                change = cleaning_form.create_bulk_edit_change()
                self.session.apply_change_to_selected_records_in_queryset(change)

            cleaning_form = None
        return self.get(request, cleaning_form=cleaning_form, change=change, *args, **kwargs)
