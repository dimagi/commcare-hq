from django.urls import reverse
from django.utils.translation import ugettext_lazy
from django.views.generic import FormView

from corehq.apps.export.forms import (
    IncrementalExportFormSet,
    IncrementalExportFormSetHelper,
)
from corehq.apps.settings.views import BaseProjectDataView


class IncrementalExportView(BaseProjectDataView, FormView):
    urlname = 'incremental_export_view'
    page_title = ugettext_lazy('Incremental Export')
    template_name = 'export/incremental_export.html'
    form_class = IncrementalExportFormSet

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # BaseIncrementalExportFormSet needs request to add to its
        # form_kwargs. IncrementalExportForm needs it to populate the
        # case export instance select box, and to set
        # IncrementalExport.domain when the model instance is saved.
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['helper'] = IncrementalExportFormSetHelper()
        return context

    def get_success_url(self):
        # On save, stay on the same page
        return reverse(self.urlname, kwargs={'domain': self.domain})

    def form_valid(self, form):
        self.object = form.save()  # Saves the forms in the formset
        return super().form_valid(form)
