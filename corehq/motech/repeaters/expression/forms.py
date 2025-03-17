from django.forms import CharField, ValidationError, ChoiceField
from django.utils.translation import gettext_lazy as _

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.filters.factory import FilterFactory
from corehq.apps.userreports.specs import FactoryContext
from corehq.apps.userreports.ui import help_text
from corehq.apps.userreports.ui.fields import JsonField
from corehq.motech.const import ALL_REQUEST_METHODS, REQUEST_POST, REQUEST_PUT
from corehq.motech.repeaters.forms import GenericRepeaterForm


LABELS = {
    'case_action_filter_expression': _("Response case action filter expression"),
    'case_action_expression': _("Response case action expression"),
}


class BaseExpressionRepeaterForm(GenericRepeaterForm):
    configured_filter = JsonField(expected_type=dict, help_text=help_text.CONFIGURED_FILTER)
    configured_expression = JsonField(expected_type=dict, required=False, help_text=_(
        "This expression is used to generate the request payload. It is required for POST, and PUT requests."
    ))
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

    def set_extra_django_form_fields(self):
        super().set_extra_django_form_fields()

        # Allow GET requests
        self.fields['request_method'] = ChoiceField(
            label=_("HTTP Request Method"),
            choices=[(rm, rm) for rm in ALL_REQUEST_METHODS],
            initial=REQUEST_POST,
            required=True,
        )

    def get_ordered_crispy_form_fields(self):
        fields = super().get_ordered_crispy_form_fields()
        return fields + [
            'url_template', 'configured_filter', 'configured_expression',
            'case_action_filter_expression', 'case_action_expression'
        ]

    def clean_configured_expression(self):
        return self._clean_expression('configured_expression')

    def clean_configured_filter(self):
        return self._clean_filter(self.cleaned_data['configured_filter'])

    def clean_case_action_expression(self):
        return self._clean_expression('case_action_expression')

    def clean_case_action_filter_expression(self):
        raw = self.cleaned_data.get('case_action_filter_expression')
        if raw:
            return self._clean_filter(raw)
        return raw

    def clean(self):
        cleaned_data = super().clean()
        request_method = self.cleaned_data['request_method']
        body_required = request_method in (REQUEST_POST, REQUEST_PUT)
        if body_required and not self.cleaned_data['configured_expression']:
            raise ValidationError({
                'configured_expression': _("This field is required for {request_method} requests.").format(
                    request_method=request_method
                ),
            })

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

    def _clean_expression(self, field_name):
        raw = self.cleaned_data.get(field_name)
        if raw:
            try:
                ExpressionFactory.from_spec(
                    raw, FactoryContext.empty(domain=self.domain)
                )
            except BadSpecError as e:
                raise ValidationError(e)

        return raw

    def _clean_filter(self, raw_expression):
        try:
            FilterFactory.from_spec(raw_expression, FactoryContext.empty(domain=self.domain))
        except BadSpecError as e:
            raise ValidationError(e)

        return raw_expression
