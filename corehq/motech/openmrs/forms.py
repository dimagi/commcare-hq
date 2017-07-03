from django.forms import forms
from django.utils.translation import ugettext as _
from corehq.apps.userreports.ui.fields import JsonField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit


class OpenmrsConfigForm(forms.Form):
    case_config = JsonField(expected_type=dict)
    form_configs = JsonField(expected_type=list)

    def __init__(self, *args, **kwargs):
        super(OpenmrsConfigForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.add_input(Submit('submit', _('Save Changes')))
