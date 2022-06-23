from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms import layout as crispy

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.userreports.models import UCRExpression
from corehq.apps.userreports.ui.fields import JsonField


class UCRExpressionForm(forms.ModelForm):
    class Meta:
        model = UCRExpression
        fields = [
            "name",
            "expression_type",
            "description",
            "definition",
        ]

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = request.domain
        self.fields['description'] = forms.CharField(required=False)
        self.fields['definition'] = JsonField(initial={"type": "property_name", "property_name": "name"})
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Expression'),
                crispy.Field('name'),
                crispy.Field('expression_type'),
                crispy.Field('description'),
                crispy.Field('definition'),
            )
        )
        self.helper.add_input(
            crispy.Submit('submit', _('Save'))
        )
        self.helper.render_required_fields = True

    def save(self, commit=True):
        self.instance.domain = self.domain
        return super().save(commit)
