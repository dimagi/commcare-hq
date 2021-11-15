from django.forms import ValidationError

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.specs import DictExpressionSpec
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.userreports.ui import help_text
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.repeaters.forms import GenericRepeaterForm


class CaseExpressionRepeaterForm(GenericRepeaterForm):
    configured_filter = JsonField(expected_type=dict, help_text=help_text.CONFIGURED_FILTER)
    configured_expression = JsonField(expected_type=dict)

    def get_ordered_crispy_form_fields(self):
        fields = super().get_ordered_crispy_form_fields()
        return fields + ['configured_filter', 'configured_expression']

    def clean_configured_expression(self):
        try:
            parsed_expression = ExpressionFactory.from_spec(
                self.cleaned_data['configured_expression'], FactoryContext.empty()
            )
            if not isinstance(parsed_expression, DictExpressionSpec):
                raise ValidationError("The configured expression must be a dict expression")
        except BadSpecError as e:
            raise ValidationError(e)

        return self.cleaned_data['configured_expression']

    def clean_configured_filter(self):
        try:
            FilterFactory.from_spec(self.cleaned_data['configured_filter'])
        except BadSpecError as e:
            raise ValidationError(e)

        return self.cleaned_data['configured_filter']
