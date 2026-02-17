from zipfile import ZipFile

from django import forms
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import openpyxl
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper

from corehq.apps.hqwebapp import crispy as hqcrispy


class ConvertTranslationsForm(forms.Form):
    upload_file = forms.FileField(label="", required=True,
                                  help_text=gettext_lazy("Upload a xls/xlsx/po/zip file"))

    def __init__(self, *args, **kwargs):
        super(ConvertTranslationsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = crispy.Layout(
            hqcrispy.B3MultiField(
                "",
                crispy.Div(
                    crispy.Field(
                        'upload_file',
                        data_bind="value: file",
                    ),
                    css_class='col-sm-4'
                ),
            ),
            StrictButton(
                gettext_lazy('Convert'),
                css_class='btn-primary',
                type='submit',
            ),
        )

    def clean_upload_file(self):
        uploaded_file = self.cleaned_data.get('upload_file')
        if uploaded_file:
            if uploaded_file.name.endswith('.xls') or uploaded_file.name.endswith('.xlsx'):
                workbook = openpyxl.load_workbook(uploaded_file)
                worksheet = workbook.worksheets[0]
                rows = [row for row in worksheet.iter_rows()]
                headers = [cell.value for cell in rows[0]]
                # ensure mandatory columns in the excel sheet
                if 'source' not in headers or 'translation' not in headers:
                    raise forms.ValidationError(_("Please ensure columns 'source' and 'translation' in the sheet"))
                return uploaded_file
            elif uploaded_file.name.endswith('.po'):
                return uploaded_file
            elif uploaded_file.name.endswith('.zip'):
                zipfile = ZipFile(uploaded_file)
                for fileinfo in zipfile.filelist:
                    filename = fileinfo.filename
                    if (not filename.endswith('.xls') and not filename.endswith('.xlsx')
                            and not filename.endswith('.po')):
                        raise forms.ValidationError(
                            _('Unexpected file passed within zip. Please upload xls/xlsx/po files.'))
                return uploaded_file
            raise forms.ValidationError(_('Unexpected file passed. Please upload xls/xlsx/po/zip file.'))


class TransifexOrganizationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(TransifexOrganizationForm, self).__init__(*args, **kwargs)
        self.initial['api_token'] = self.instance.plaintext_api_token
