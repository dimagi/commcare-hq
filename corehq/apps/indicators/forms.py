from django import forms
from django.utils.translation import ugettext_noop, ugettext as _
from bootstrap3_crispy import bootstrap as twbs
from bootstrap3_crispy.helper import FormHelper
from bootstrap3_crispy import layout as crispy
from corehq.apps.style.crispy import FormActions


class ImportIndicatorsFromJsonFileForm(forms.Form):
    json_file = forms.FileField(
        label=ugettext_noop("Exported File"),
        required=False,
    )
    override_existing = forms.BooleanField(
        label=ugettext_noop("Override Existing Indicators"),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super(ImportIndicatorsFromJsonFileForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'POST'
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-8'
        self.helper.layout = crispy.Layout(
            crispy.Field('json_file'),
            crispy.Field('override_existing'),
            FormActions(
                twbs.StrictButton(_("Import Indicators"),
                                  type='submit',
                                  css_class='btn-primary'),
            ),

        )
