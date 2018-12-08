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

from corehq.apps.app_manager.dbaccessors import get_available_versions_for_app
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain


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


class AppTranslationsForm(forms.Form):
    app_id = forms.ChoiceField(label=ugettext_lazy("Application"), choices=(), required=True)
    version = forms.IntegerField(label=ugettext_lazy("Application Version"), required=False,
                                 help_text=ugettext_lazy("Leave blank to use current saved state"))
    use_version_postfix = forms.MultipleChoiceField(
        choices=[
            ('yes', 'Track resources per version'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        initial='no',
        help_text=ugettext_lazy("Check this if you want to maintain different resources separately for different "
                                "versions of the application. Leave it unchecked for continuous update to the same "
                                "set of resources.")
    )
    transifex_project_slug = forms.ChoiceField(label=ugettext_lazy("Trasifex project"), choices=(),
                                               required=True)
    target_lang = forms.ChoiceField(label=ugettext_lazy("Translated Language"),
                                    choices=([(None, ugettext_lazy('Select Translated Language'))] +
                                             langcodes.get_all_langs_for_select()),
                                    required=False,
                                    )
    action = forms.CharField(widget=forms.HiddenInput)
    perform_translated_check = forms.BooleanField(label=ugettext_lazy("Check for translation completion"),
                                                  help_text=ugettext_lazy(
                                                      "Check for translation completion before pulling files"),
                                                  required=False,
                                                  initial=True)

    def __init__(self, domain, *args, **kwargs):
        super(AppTranslationsForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-4 col-md-4 col-lg-3'
        self.helper.field_class = 'col-sm-6 col-md-6 col-lg-5'

        self.fields['app_id'].choices = tuple((app.id, app.name) for app in get_brief_apps_in_domain(domain))
        if settings.TRANSIFEX_DETAILS:
            self.fields['transifex_project_slug'].choices = (
                tuple((slug, slug)
                      for slug in settings.TRANSIFEX_DETAILS.get('project').get(domain))
            )
        form_fields = self.form_fields()
        form_fields.append(hqcrispy.Field(StrictButton(
            ugettext_lazy("Submit"),
            type="submit",
            css_class="btn btn-primary btn-lg disable-on-submit",
            onclick="return confirm('%s')" % ugettext_lazy("Please confirm that you want to proceed?")
        )))
        self.helper.layout = crispy.Layout(
            *form_fields
        )
        self.fields['action'].initial = self.form_action

    def form_fields(self):
        return [
            hqcrispy.Field('app_id'),
            hqcrispy.Field('version'),
            hqcrispy.Field('use_version_postfix'),
            hqcrispy.Field('transifex_project_slug'),
            hqcrispy.Field('action')
        ]

    def clean(self):
        # ensure target lang when translation check requested during pull
        # to check for translation completion
        cleaned_data = super(AppTranslationsForm, self).clean()
        version = cleaned_data['version']
        if version:
            app_id = cleaned_data['app_id']
            available_versions = get_available_versions_for_app(self.domain, app_id)
            if version not in available_versions:
                self.add_error('version', ugettext_lazy('Version not available for app'))
        if (not cleaned_data['target_lang'] and
                (cleaned_data['action'] == "pull" and cleaned_data['perform_translated_check'])):
            self.add_error('target_lang', ugettext_lazy('Target lang required to confirm translation completion'))
        return cleaned_data

    @classmethod
    def form_for(cls, form_action):
        if form_action == 'create':
            return CreateAppTranslationsForm
        elif form_action == 'update':
            return UpdateAppTranslationsForm
        elif form_action == 'push':
            return PushAppTranslationsForm
        elif form_action == 'pull':
            return PullAppTranslationsForm
        elif form_action == 'backup':
            return BackUpAppTranslationsForm
        elif form_action == 'delete':
            return DeleteAppTranslationsForm


class CreateAppTranslationsForm(AppTranslationsForm):
    form_action = 'create'
    source_lang = forms.ChoiceField(label=ugettext_lazy("Source Language on Transifex"),
                                    choices=langcodes.get_all_langs_for_select(),
                                    initial="en"
                                    )

    def form_fields(self):
        form_fields = super(CreateAppTranslationsForm, self).form_fields()
        form_fields.append(hqcrispy.Field('source_lang', css_class="ko-select2"))
        return form_fields


class UpdateAppTranslationsForm(CreateAppTranslationsForm):
    form_action = 'update'


class PushAppTranslationsForm(AppTranslationsForm):
    form_action = 'push'

    def form_fields(self):
        form_fields = super(PushAppTranslationsForm, self).form_fields()
        form_fields.append(hqcrispy.Field('target_lang', css_class="ko-select2"))
        return form_fields


class PullAppTranslationsForm(AppTranslationsForm):
    form_action = 'pull'
    lock_translations = forms.BooleanField(label=ugettext_lazy("Lock resources"),
                                           help_text=ugettext_lazy(
                                               "Lock translations for resources that are being pulled"),
                                           required=False,
                                           initial=False)

    def form_fields(self):
        form_fields = super(PullAppTranslationsForm, self).form_fields()
        form_fields.extend([
            hqcrispy.Field('target_lang', css_class="ko-select2"),
            hqcrispy.Field('lock_translations'),
            hqcrispy.Field('perform_translated_check'),
        ])
        return form_fields


class DeleteAppTranslationsForm(AppTranslationsForm):
    form_action = 'delete'

    def form_fields(self):
        form_fields = super(DeleteAppTranslationsForm, self).form_fields()
        form_fields.append(hqcrispy.Field('perform_translated_check'))
        return form_fields


class BackUpAppTranslationsForm(AppTranslationsForm):
    form_action = 'backup'
