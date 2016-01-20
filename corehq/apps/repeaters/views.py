from django.core.urlresolvers import reverse

from corehq.apps.domain.views import AddRepeaterView
from corehq.apps.style.decorators import use_select2
from .forms import CaseRepeaterForm


class AddCaseRepeaterView(AddRepeaterView):
    urlname = 'add_case_repeater'
    repeater_form_class = CaseRepeaterForm
    template_name = 'repeaters/add_case_repeater.html'

    @use_select2
    def dispatch(self, request, *args, **kwargs):
        return super(AddCaseRepeaterView, self).dispatch(request, *args, **kwargs)

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def make_repeater(self):
        repeater = super(AddCaseRepeaterView, self).make_repeater()
        repeater.white_listed_case_types = self.add_repeater_form.cleaned_data['white_listed_case_types']
        repeater.black_listed_users = self.add_repeater_form.cleaned_data['black_listed_users']
        return repeater
