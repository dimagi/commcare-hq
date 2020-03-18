from django import forms
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton

from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.locations.models import LocationType
from corehq.util.workbook_json.excel import get_workbook


class LocationRationalizationValidateForm(forms.Form):
    file = forms.FileField(label="", required=True,
                           help_text=ugettext_lazy("Upload xlsx file"))

    def __init__(self, *args, **kwargs):
        self.location_types = kwargs.pop('location_types', None)
        super(LocationRationalizationValidateForm, self).__init__(*args, **kwargs)
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


class LocationRationalizationTemplateForm(forms.Form):
    location_id = forms.CharField(label=ugettext_lazy("Location"), widget=forms.widgets.Select(choices=[]),
                                  required=True)
    location_type = forms.ChoiceField(label=ugettext_lazy("Location Type"), choices=(), required=True,
                                      help_text=_("the location type each row should represent in download"
                                                  " or ideally the smallest possible location type"))

    def __init__(self, domain, *args, **kwargs):
        self.domain = domain
        super(LocationRationalizationTemplateForm, self).__init__(*args, **kwargs)
        self.fields['location_type'].choices = self._location_type_choices()
        self.helper = HQFormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = crispy.Layout(
            crispy.Field('location_id', id='location_search_select'),
            crispy.Field('location_type'),
            StrictButton(ugettext_lazy('Download'), css_class='btn-primary', type='submit'),
        )
        self.location_id = None

    def _location_type_choices(self):
        return [(loc_type.code, loc_type.name)
                for loc_type in LocationType.objects.by_domain(self.domain)]
