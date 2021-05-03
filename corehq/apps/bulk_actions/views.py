from django.urls import reverse
from django.utils.translation import ugettext_lazy, ugettext as _

from corehq.apps.settings.views import BaseProjectDataView

from corehq.apps.bulk_actions.forms import BulkActionForm


class ListBulkActionsView(BaseProjectDataView):
    urlname = 'list_bulk_action'
    page_title = ugettext_lazy('Bulk Actions')
    template_name = 'bulk_actions/list.html'


class EditBulkActionView(BaseProjectDataView):
    urlname = 'edit_bulk_action'
    page_title = ugettext_lazy('Edit Bulk Action')
    template_name = 'bulk_actions/edit.html'

    @property
    def form(self):
        if self.request.method == 'POST':
            return BulkActionForm(self.request.POST)
        return BulkActionForm()

    @property
    def page_context(self):
        return {
            'form': self.form
        }

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)
