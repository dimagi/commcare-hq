from django import forms
from django.forms import inlineformset_factory
from django.urls import reverse
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _

from crispy_forms import layout as crispy

from corehq.apps.hqwebapp.crispy import HQFormHelper, FieldWithAddons
from corehq.apps.userreports.models import UCRExpression
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    ConfigurableApiValidation, ApiBackendOptions,
)


class ConfigurableAPICreateForm(forms.ModelForm):
    fieldset_title = _('Create a new API')

    class Meta:
        model = ConfigurableAPI
        fields = [
            "name",
            "description",
            "filter_expression",
            "transform_expression",
            "backend",
        ]
        labels = {
            "backend": _("Input Data Type")
        }
        widgets = {
            "description": forms.TextInput(),
            "backend": forms.Select(choices=ApiBackendOptions.choices)
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = request.domain
        transform_expression_field = self.fields['transform_expression']
        transform_expression_field.queryset = UCRExpression.objects.get_expressions_for_domain(self.domain)
        self.fields['filter_expression'].queryset = UCRExpression.objects.get_filters_for_domain(self.domain)
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                self.fieldset_title,
                crispy.Field('name'),
                crispy.Field('description'),
                crispy.Field('backend'),
                FieldWithAddons('filter_expression', post_addon=_expression_link(self.domain)),
                FieldWithAddons('transform_expression', post_addon=_expression_link(self.domain)),
            )
        )
        self.helper.render_required_fields = True
        self.add_to_helper()

    def add_to_helper(self):
        self.helper.add_input(
            crispy.Submit('submit', _('Save'))
        )

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)


class ConfigurableAPIUpdateForm(ConfigurableAPICreateForm):
    fieldset_title = _('Basic Configuration')

    def add_to_helper(self):
        self.helper.form_tag = False


ApiValidationFormSet = inlineformset_factory(
    ConfigurableAPI, ConfigurableApiValidation, fields=("name", "expression", "message"),
    extra=0, can_delete=True
)


def _expression_link(domain):
    return SafeString(
        '<a href="{url}" target="_blank" title="{title}">'
        '<i class="fa-solid fa-up-right-from-square"></i></a>'.format(
            url=reverse('ucr_expressions', args=(domain,)),
            title=_("Filters and Expressions")
        )
    )
