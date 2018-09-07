from __future__ import absolute_import
from __future__ import unicode_literals
import openpyxl
import langcodes

from django import forms
from django.conf import settings
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms import bootstrap as twbscrispy
from django.utils.translation import ugettext as _, ugettext_lazy

from corehq.apps.hqwebapp import crispy as hqcrispy


class ConvertTranslationsForm(forms.Form):
    upload_file = forms.FileField(label="", required=True)

    def __init__(self, *args, **kwargs):
        super(ConvertTranslationsForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = crispy.Layout(
            crispy.Field(
                'upload_file',
                data_bind="value: file",
            ),
            StrictButton(
                ugettext_lazy('Convert'),
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
            raise forms.ValidationError(_('Unexpected file passed. Please upload xls/xlsx/po file.'))


class PullResourceForm(forms.Form):
    transifex_project_slug = forms.ChoiceField(label=ugettext_lazy("Trasifex project"), choices=(),
                                               required=True)
    target_lang = forms.ChoiceField(label=ugettext_lazy("Target Language"),
                                    choices=langcodes.get_all_langs_for_select(),
                                    initial="en"
                                    )
    resource_slug = forms.CharField(label=_("Resource Slug"))

    def __init__(self, domain, *args, **kwargs):
        super(PullResourceForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        if settings.TRANSIFEX_DETAILS:
            self.fields['transifex_project_slug'].choices = (
                tuple((slug, slug)
                      for slug in settings.TRANSIFEX_DETAILS.get('project').get(domain))
            )
        self.helper.layout = crispy.Layout(
            'transifex_project_slug',
            crispy.Field('target_lang', css_class="ko-select2"),
            'resource_slug',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    ugettext_lazy("Submit"),
                    type="submit",
                    css_class="btn-primary",
                )
            )
        )
