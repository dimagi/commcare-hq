from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from corehq.motech.repeaters.expression.forms import BaseExpressionRepeaterForm
from corehq.motech.repeaters.views import AddRepeaterView, EditRepeaterView


class BaseExpressionRepeaterView(AddRepeaterView):
    repeater_form_class = BaseExpressionRepeaterForm

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
        repeater.case_action_filter_expression = (
            self.add_repeater_form.cleaned_data['case_action_filter_expression']
        )
        repeater.case_action_expression = (
            self.add_repeater_form.cleaned_data['case_action_expression']
        )
        return repeater


class AddCaseExpressionRepeaterView(BaseExpressionRepeaterView):
    urlname = 'add_case_expression_repeater'


class EditCaseExpressionRepeaterView(EditRepeaterView, BaseExpressionRepeaterView):
    urlname = 'edit_case_expression_repeater'
    page_title = _("Edit Case Repeater")


class AddFormExpressionRepeaterView(BaseExpressionRepeaterView):
    urlname = 'add_form_expression_repeater'


class EditFormExpressionRepeaterView(EditRepeaterView, BaseExpressionRepeaterView):
    urlname = 'edit_form_expression_repeater'
    page_title = _('Edit Form Repeater')


class AddArcGISFormExpressionRepeaterView(BaseExpressionRepeaterView):
    urlname = 'add_arcgis_form_expression_repeater'


class EditArcGISFormExpressionRepeaterView(EditRepeaterView, BaseExpressionRepeaterView):
    urlname = 'edit_arcgis_form_expression_repeater'
    page_title = _("Edit ArcGIS Form Repeater")
