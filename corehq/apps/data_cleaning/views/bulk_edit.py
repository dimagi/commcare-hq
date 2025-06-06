from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy
from django.views.generic import TemplateView

from corehq.apps.data_cleaning.decorators import require_bulk_data_cleaning_cases
from corehq.apps.data_cleaning.forms.bulk_edit import EditSelectedRecordsForm
from corehq.apps.data_cleaning.views.mixins import BulkEditSessionViewMixin
from corehq.apps.domain.decorators import LoginAndDomainMixin
from corehq.apps.domain.views import DomainViewMixin
from corehq.apps.hqwebapp.decorators import use_bootstrap5
from corehq.util.htmx_action import HqHtmxActionMixin, hq_hx_action


@method_decorator(
    [
        use_bootstrap5,
        require_bulk_data_cleaning_cases,
    ],
    name='dispatch',
)
class EditSelectedRecordsFormView(
    BulkEditSessionViewMixin, LoginAndDomainMixin, DomainViewMixin, HqHtmxActionMixin, TemplateView
):
    urlname = 'bulk_edit_selected_records_form'
    template_name = 'data_cleaning/forms/edit_selected_records_form.html'
    session_not_found_message = gettext_lazy('Cannot load edit selected records form, session was not found.')

    def get_context_data(self, form=None, change=None, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'container_id': 'edit-selected-records',
                'form': form or EditSelectedRecordsForm(self.session),
                'are_bulk_edits_allowed': self.session.are_bulk_edits_allowed(),
                'change': change,
            }
        )
        return context

    @hq_hx_action('post')
    def create_bulk_edit_change(self, request, *args, **kwargs):
        form = EditSelectedRecordsForm(self.session, request.POST)
        change = None
        if form.is_valid():
            change = self.session.apply_change_to_selected_records(form.get_bulk_edit_change())
            response = self.get(request, form=None, change=change, *args, **kwargs)
            return self.include_gtm_event_with_response(
                response,
                'bulk_edit_change_created',
                {
                    'edit_action': form.cleaned_data.get('edit_action', None),
                },
            )
        return self.get(request, form=form, change=change, *args, **kwargs)
