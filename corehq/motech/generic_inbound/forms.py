from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _

from crispy_forms import layout as crispy

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.userreports.models import UCRExpression
from corehq.motech.generic_inbound.models import (
    ConfigurableAPI,
    ConfigurableApiValidation,
)


class ConfigurableAPICreateForm(forms.ModelForm):
    fieldset_title = _('Create a new API')

    class Meta:
        model = ConfigurableAPI
        fields = [
            "name",
            "description",
            "transform_expression",
        ]
        widgets = {
            'description': forms.TextInput(),
        }

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = request.domain
        self.fields['transform_expression'] = forms.ModelChoiceField(
            queryset=UCRExpression.objects.get_expressions_for_domain(self.domain)
        )
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                self.fieldset_title,
                crispy.Field('name'),
                crispy.Field('description'),
                crispy.Field('transform_expression'),
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
