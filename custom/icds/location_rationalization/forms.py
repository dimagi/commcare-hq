from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.util.workbook_json.excel import get_workbook


class LocationRationalizationRequestForm(forms.Form):
    file = forms.FileField(label="", required=True,
                           help_text=ugettext_lazy("Upload xlsx file"))

    def __init__(self, *args, **kwargs):
        if 'location_types' in kwargs:
            self.location_types = kwargs.pop('location_types')
        super(LocationRationalizationRequestForm, self).__init__(*args, **kwargs)
        self.helper = HQFormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = crispy.Layout(
            crispy.Field(ugettext_lazy('file'), data_bind="value: file"),
            StrictButton(ugettext_lazy('Upload'), css_class='btn-primary', type='submit'),
        )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')
        if not uploaded_file.name.endswith('.xlsx'):
            raise forms.ValidationError(_('Unexpected file passed. Please upload xlsx file only.'))
        self._validate_file(uploaded_file)
        return uploaded_file

    def _validate_file(self, uploaded_file):
        # ensure mandatory columns in the excel sheet
        workbook = get_workbook(uploaded_file)
        worksheet = workbook.worksheets[0]
        headers = worksheet.fieldnames
        expected_headers = []
        for location_type in self.location_types:
            expected_headers.extend([f'old_{location_type}', f'new_{location_type}'])
        missing_headers = set(expected_headers) - set(headers)
        if missing_headers:
            raise forms.ValidationError(_("Missing following columns in sheet: {columns}").format(
                columns=", ".join(missing_headers)
            ))
