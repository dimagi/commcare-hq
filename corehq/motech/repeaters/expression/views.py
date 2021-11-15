from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from corehq.motech.repeaters.expression.forms import CaseExpressionRepeaterForm
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView


class AddCaseExpressionRepeaterView(AddRepeaterView):
    urlname = 'add_case_expression_repeater'
    repeater_form_class = CaseExpressionRepeaterForm

    @property
    def page_url(self):
        return reverse(self.urlname, args=[self.domain])

    def set_repeater_attr(self, repeater, cleaned_data):
        repeater = super().set_repeater_attr(repeater, cleaned_data)
        repeater.configured_filter = (
            self.add_repeater_form.cleaned_data['configured_filter'])
        repeater.configured_expression = (
            self.add_repeater_form.cleaned_data['configured_expression'])
        return repeater


class EditCaseExpressionRepeaterView(EditRepeaterView, AddCaseExpressionRepeaterView):
    urlname = 'edit_case_expression_repeater'
    page_title = _("Edit Case Repeater")
