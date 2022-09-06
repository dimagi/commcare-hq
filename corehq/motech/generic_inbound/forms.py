from crispy_forms import layout as crispy
from django import forms
from django.utils.translation import gettext_lazy as _

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.userreports.models import UCRExpression
from corehq.motech.generic_inbound.models import ConfigurableAPI


class ConfigurableAPIForm(forms.ModelForm):
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
            queryset=UCRExpression.objects.get_expression_models_for_domain(self.domain)
        )
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Create a new API'),
                crispy.Field('name'),
                crispy.Field('description'),
                crispy.Field('transform_expression'),
            )
        )
        self.helper.add_input(
            crispy.Submit('submit', _('Save'))
        )
        self.helper.render_required_fields = True

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)
