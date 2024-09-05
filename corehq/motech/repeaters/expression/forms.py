from django.forms import CharField, ValidationError
from django.utils.translation import gettext_lazy as _

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.userreports.ui import help_text
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.repeaters.forms import GenericRepeaterForm


LABELS = {
    'case_action_filter_expression': _("Response case action filter expression"),
    'case_action_expression': _("Response case action expression"),
}


class BaseExpressionRepeaterForm(GenericRepeaterForm):
    configured_filter = JsonField(expected_type=dict, help_text=help_text.CONFIGURED_FILTER)
    configured_expression = JsonField(expected_type=dict)
    url_template = CharField(
        required=False,
        help_text=_("Items to add to the end of the URL. Please see the documentation for more information.")
    )

    case_action_filter_expression = JsonField(
        expected_type=dict, required=False,
        label=LABELS['case_action_filter_expression'],
        help_text=_(
            "Use this to determine if the response should create or update a case. "
            "If left blank, no action will be taken. "
            'For more info see <a target="_blank" href="'
            'https://dimagi.atlassian.net/wiki/spaces/GS/pages/2146602964/Configurable+Repeaters'
            '">these docs</a>'
        )
    )
    case_action_expression = JsonField(
        expected_type=dict, required=False,
        label=LABELS['case_action_expression'],
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
            'case_action_filter_expression', 'case_action_expression'
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

    def clean_case_action_expression(self):
        raw = self.cleaned_data.get('case_action_expression')
        if raw:
            try:
                ExpressionFactory.from_spec(
                    raw, FactoryContext.empty(domain=self.domain)
                )
            except BadSpecError as e:
                raise ValidationError(e)

        return raw

    def clean_case_action_filter_expression(self):
        raw = self.cleaned_data.get('case_action_filter_expression')
        if raw:
            try:
                FilterFactory.from_spec(raw)
            except BadSpecError as e:
                raise ValidationError(e)

        return raw

    def clean(self):
        cleaned_data = super().clean()
        case_filter = bool(cleaned_data.get('case_action_filter_expression'))
        case_operation = bool(cleaned_data.get('case_action_expression'))
        if case_filter ^ case_operation:
            field = 'case_action_expression' if case_filter else 'case_action_filter_expression'
            other = 'case_action_filter_expression' if case_filter else 'case_action_expression'
            raise ValidationError({
                field: _("This field is required when '{other}' is provided").format(
                    other=LABELS[other]
                ),
            })
        return cleaned_data
