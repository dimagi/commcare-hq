from django.forms import CharField, ValidationError
from django.utils.translation import gettext_lazy as _

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.userreports.ui import help_text
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.repeaters.forms import GenericRepeaterForm


class CaseExpressionRepeaterForm(GenericRepeaterForm):
    configured_filter = JsonField(expected_type=dict, help_text=help_text.CONFIGURED_FILTER)
    configured_expression = JsonField(expected_type=dict)
    url_template = CharField(
        required=False,
        help_text=_("Items to add to the end of the URL. Please see the documentation for more information.")
    )

    update_case_filter_expression = JsonField(
        expected_type=dict, required=False,
        label=_("Response case update filter expression"),
        help_text=_(
            "Use this to determine if the response should create or update a case. "
            "If left blank, the response will be ignored. "
            'For more info see <a target="_blank" href="'
            'https://dimagi.atlassian.net/wiki/spaces/GS/pages/2146602964/Configurable+Repeaters'
            '">these docs</a>'
        )
    )
    update_case_expression = JsonField(
        expected_type=dict, required=False,
        label=_("Response case update expression"),
        help_text=_(
            "Use this to create a Case API payload which will be used to create or update a case. "
            'For more info see <a target="_blank" href="'
            'https://dimagi.atlassian.net/wiki/spaces/GS/pages/2146602964/Configurable+Repeaters'
            '">these docs</a>'
        )
    )

    def get_ordered_crispy_form_fields(self):
        fields = super().get_ordered_crispy_form_fields()
        return fields + [
            'url_template', 'configured_filter', 'configured_expression',
            'update_case_filter_expression', 'update_case_expression'
        ]

    def clean_configured_expression(self):
        try:
            ExpressionFactory.from_spec(
                self.cleaned_data['configured_expression'], FactoryContext.empty(domain=self.domain)
            )
        except BadSpecError as e:
            raise ValidationError(e)

        return self.cleaned_data['configured_expression']

    def clean_configured_filter(self):
        try:
            FilterFactory.from_spec(self.cleaned_data['configured_filter'])
        except BadSpecError as e:
            raise ValidationError(e)

        return self.cleaned_data['configured_filter']
