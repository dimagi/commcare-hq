from django.urls import reverse
from django.utils.translation import gettext_lazy as _

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
            self.add_repeater_form.cleaned_data['configured_filter']
        )
        repeater.configured_expression = (
            self.add_repeater_form.cleaned_data['configured_expression']
        )
        repeater.url_template = self.add_repeater_form.cleaned_data['url_template']
        repeater.update_case_filter_expression = (
            self.add_repeater_form.cleaned_data['update_case_filter_expression']
        )
        repeater.update_case_expression = (
            self.add_repeater_form.cleaned_data['update_case_expression']
        )
        return repeater


class EditCaseExpressionRepeaterView(EditRepeaterView, AddCaseExpressionRepeaterView):
    urlname = 'edit_case_expression_repeater'
    page_title = _("Edit Case Repeater")


class AddArcGISFormExpressionRepeaterView(AddCaseExpressionRepeaterView):
    urlname = 'add_arcgis_form_expression_repeater'


class EditArcGISFormExpressionRepeaterView(EditRepeaterView, AddCaseExpressionRepeaterView):
    urlname = 'edit_arcgis_form_expression_repeater'
    page_title = _("Edit ArcGIS Form Repeater")
