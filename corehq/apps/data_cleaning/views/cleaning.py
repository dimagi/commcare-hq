from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin


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
            'session': self.session,  # temporarily calling this here so that access tests pass
        })
        return context
