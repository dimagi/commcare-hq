from django import forms
from django.utils.translation import ugettext as _

from crispy_forms import layout as crispy
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy


class MigrationForm(forms.Form):
    case_type = forms.CharField()
    migration_xml = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super(MigrationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-10'
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _("Case Migration"),
                'case_type',
                'migration_xml',
            ),
            hqcrispy.FormActions(
                crispy.ButtonHolder(
                    crispy.Submit('submit', _("Submit"))
                )
            )
        )
