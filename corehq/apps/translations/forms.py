from zipfile import ZipFile

from django import forms
from django.forms.widgets import Select
from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

import openpyxl
from crispy_forms import bootstrap as twbscrispy
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from memoized import memoized

import langcodes
from corehq.apps.app_manager.dbaccessors import (
    get_available_versions_for_app,
    get_brief_apps_in_domain,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.hqwebapp import crispy as hqcrispy
from corehq.apps.hqwebapp.crispy import HQFormHelper
from corehq.apps.translations.exceptions import (
    TransifexProjectMigrationInvalidUpload,
)
from corehq.apps.translations.integrations.transifex.exceptions import (
    InvalidProjectMigration,
)
from corehq.apps.translations.integrations.transifex.project_migrator import (
    ProjectMigrator,
)
from corehq.apps.translations.models import (
    TransifexBlacklist,
    TransifexProject,
)
from corehq.motech.utils import b64_aes_decrypt
from corehq.util.workbook_json.excel import WorkbookJSONReader


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


class PullResourceForm(forms.Form):
    transifex_project_slug = forms.ChoiceField(label=gettext_lazy("Transifex project"), choices=())
    target_lang = forms.ChoiceField(label=gettext_lazy("Target Language"),
                                    choices=langcodes.get_all_langs_for_select(),
                                    initial="en"
                                    )
    resource_slug = forms.CharField(label=_("Resource Slug"), required=False,
                                    help_text=gettext_lazy("Leave blank to fetch full project")
                                    )

    def __init__(self, domain, *args, **kwargs):
        super(PullResourceForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-3 col-md-4 col-lg-2'
        self.helper.field_class = 'col-sm-4 col-md-5 col-lg-3'

        projects = TransifexProject.objects.filter(domain=domain).all()
        if projects:
            self.fields['transifex_project_slug'].choices = (
                tuple((project.slug, project) for project in projects)
            )
        self.helper.layout = crispy.Layout(
            crispy.Field('transifex_project_slug', css_class="hqwebapp-select2"),
            crispy.Field('target_lang', css_class="hqwebapp-select2"),
            'resource_slug',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Submit"),
                    type="submit",
                    css_class="btn-primary",
                )
            )
        )


class AppTranslationsForm(forms.Form):
    app_id = forms.ChoiceField(label=gettext_lazy("Application"), choices=(), required=True)
    version = forms.IntegerField(label=gettext_lazy("Application Version"), required=False,
                                 help_text=gettext_lazy("Leave blank to use current saved state"),
                                 widget=Select(choices=[]))
    use_version_postfix = forms.MultipleChoiceField(
        choices=[
            ('yes', 'Track resources per version'),
        ],
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        initial='no',
        help_text=gettext_lazy("Check this if you want to maintain different resources separately for different "
                               "versions of the application. Leave it unchecked for continuous update to the same"
                               " set of resources")
    )
    transifex_project_slug = forms.ChoiceField(label=gettext_lazy("Transifex project"), choices=(),
                                               required=True)
    target_lang = forms.ChoiceField(label=gettext_lazy("Translated Language"),
                                    choices=([(None, gettext_lazy('Select Translated Language'))]
                                             + langcodes.get_all_langs_for_select()),
                                    required=False,
                                    )
    action = forms.CharField(widget=forms.HiddenInput)
    perform_translated_check = forms.BooleanField(
        label=gettext_lazy("Confirm that resources are completely translated before performing request"),
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
        projects = TransifexProject.objects.filter(domain=domain).all()
        if projects:
            self.fields['transifex_project_slug'].choices = (
                tuple((project.slug, project) for project in projects)
            )
        form_fields = self.form_fields()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "",
                *form_fields
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Submit"),
                    type="submit",
                    css_class="btn btn-primary disable-on-submit",
                    onclick="return confirm('%s')" % gettext_lazy("Please confirm that you want to proceed?")
                )
            )
        )
        self.fields['action'].initial = self.form_action

    def form_fields(self):
        return [
            crispy.Field('app_id', css_class="hqwebapp-select2"),
            'version',
            'use_version_postfix',
            crispy.Field('transifex_project_slug', css_class="hqwebapp-select2"),
            'action',
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
                self.add_error('version', gettext_lazy('Version not available for app'))
        if (not cleaned_data['target_lang']
                and (cleaned_data['action'] == "pull" and cleaned_data['perform_translated_check'])):
            self.add_error('target_lang', gettext_lazy('Target lang required to confirm translation completion'))
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
    source_lang = forms.ChoiceField(label=gettext_lazy("Source Language on Transifex"),
                                    choices=langcodes.get_all_langs_for_select(),
                                    initial="en"
                                    )

    def form_fields(self):
        form_fields = super(CreateAppTranslationsForm, self).form_fields()
        form_fields.append(crispy.Field('source_lang', css_class="hqwebapp-select2"))
        return form_fields


class UpdateAppTranslationsForm(CreateAppTranslationsForm):
    form_action = 'update'


class PushAppTranslationsForm(AppTranslationsForm):
    form_action = 'push'

    def form_fields(self):
        form_fields = super(PushAppTranslationsForm, self).form_fields()
        form_fields.append(crispy.Field('target_lang', css_class="hqwebapp-select2"))
        return form_fields


class PullAppTranslationsForm(AppTranslationsForm):
    form_action = 'pull'
    lock_translations = forms.BooleanField(label=gettext_lazy("Lock translations for resources that are being "
                                                              "pulled"),
                                           help_text=gettext_lazy("Please note that this will lock the resource"
                                                                  " for all languages"),
                                           required=False,
                                           initial=False)

    def form_fields(self):
        form_fields = super(PullAppTranslationsForm, self).form_fields()
        form_fields.extend([
            crispy.Field('target_lang', css_class="hqwebapp-select2"),
            'lock_translations',
            'perform_translated_check',
        ])
        return form_fields


class DeleteAppTranslationsForm(AppTranslationsForm):
    form_action = 'delete'

    def form_fields(self):
        form_fields = super(DeleteAppTranslationsForm, self).form_fields()
        form_fields.append('perform_translated_check')
        return form_fields


class DownloadAppTranslationsForm(CreateAppTranslationsForm):
    """Used to download the files that are being uploaded to Transifex."""

    form_action = 'download'


class BackUpAppTranslationsForm(AppTranslationsForm):
    form_action = 'backup'


class TransifexOrganizationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(TransifexOrganizationForm, self).__init__(*args, **kwargs)
        self.initial['api_token'] = b64_aes_decrypt(self.instance.api_token)


class AddTransifexBlacklistForm(forms.ModelForm):
    app_id = forms.ChoiceField(label=gettext_lazy("Application"), choices=(), required=True)
    action = forms.CharField(widget=forms.HiddenInput)
    domain = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, domain, *args, **kwargs):
        super(AddTransifexBlacklistForm, self).__init__(*args, **kwargs)
        self.helper = hqcrispy.HQFormHelper()

        self.fields['app_id'].choices = tuple((app.id, app.name) for app in get_brief_apps_in_domain(domain))
        form_fields = [
            'app_id',
            'module_id',
            'field_type',
            'field_name',
            'display_text',
            'domain',
            'action',
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Add"),
                    type="submit",
                    css_class="btn-primary disable-on-submit",
                )
            )
        ]
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                gettext_lazy("Add translation to blacklist"),
                *form_fields
            ),
        )
        self.fields['action'].initial = 'blacklist'
        self.fields['domain'].initial = domain

    def clean(self):
        cleaned_data = super(AddTransifexBlacklistForm, self).clean()
        app_id = cleaned_data.get('app_id')
        module_id = cleaned_data.get('module_id')
        field_type = cleaned_data.get('field_type')

        self._check_module_in_app(app_id, module_id)
        self._check_module_not_ui_translation(module_id, field_type)
        self._check_module_for_case_list_detail(module_id, field_type)

    def _check_module_in_app(self, app_id, module_id):
        if module_id:
            app_json = Application.get_db().get(app_id)
            for module in app_json['modules']:
                if module_id == module['unique_id']:
                    break
            else:
                self.add_error('module_id', "Module {} not found in app {}".format(module_id, app_json['name']))

    def _check_module_not_ui_translation(self, module_id, field_type):
        if module_id and field_type == 'ui':
            self.add_error(field=None, error=forms.ValidationError({
                'module_id': 'Leave Module ID blank for UI translations',
                'field_type': 'Specify "Case List" or "Case Detail" for a module. '
                              'UI translations apply to the whole app.',
            }))

    def _check_module_for_case_list_detail(self, module_id, field_type):
        if not module_id and field_type != 'ui':
            self.add_error('module_id', 'Module ID must be given for "Case List" or "Case Detail"')

    class Meta(object):
        model = TransifexBlacklist
        fields = '__all__'


class MigrateTransifexProjectForm(forms.Form):
    TYPE_HEADER = "Type"
    OLD_ID_HEADER = "Old-ID"
    NEW_ID_HEADER = "New-ID"
    from_app_id = forms.ChoiceField(label=gettext_lazy("From Application"), choices=(), required=True)
    to_app_id = forms.ChoiceField(label=gettext_lazy("To Application"), choices=(), required=True)
    transifex_project_slug = forms.ChoiceField(label=gettext_lazy("Transifex project"), choices=(),
                                               required=True)
    mapping_file = forms.FileField(label="", required=True,
                                   help_text=gettext_lazy("Upload a xls file mapping old to new ids"))

    def __init__(self, domain, *args, **kwargs):
        super(MigrateTransifexProjectForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self._set_choices()
        self.helper = HQFormHelper()
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                "Migrate Project",
                crispy.Field('from_app_id', css_class="hqwebapp-select2"),
                crispy.Field('to_app_id', css_class="hqwebapp-select2"),
                crispy.Field('transifex_project_slug'),
                crispy.Field('mapping_file'),
            ),
            hqcrispy.FormActions(
                twbscrispy.StrictButton(
                    gettext_lazy("Submit"),
                    type="submit",
                    css_class="btn btn-primary disable-on-submit",
                    onclick="return confirm('%s')" % gettext_lazy(
                        "We recommend taking a backup if you have not already."
                        "Please confirm that you want to proceed?")
                )
            )
        )

    def _set_choices(self):
        app_id_choices = tuple((app.id, app.name) for app in get_brief_apps_in_domain(self.domain))
        self.fields['from_app_id'].choices = app_id_choices
        self.fields['to_app_id'].choices = app_id_choices
        projects = TransifexProject.objects.filter(domain=self.domain).all()
        if projects:
            self.fields['transifex_project_slug'].choices = (
                tuple((project.slug, project) for project in projects)
            )

    def _validate_worksheet_headers(self, headers):
        if (self.TYPE_HEADER not in headers
                or self.OLD_ID_HEADER not in headers
                or self.NEW_ID_HEADER not in headers):
            raise TransifexProjectMigrationInvalidUpload(
                _(
                    "Could not load file. Please ensure columns {type_header}, "
                    "{old_id_header} and {new_id_header} are present"
                ).format(
                    type_header=self.TYPE_HEADER,
                    old_id_header=self.OLD_ID_HEADER,
                    new_id_header=self.NEW_ID_HEADER,
                ))

    def _validate_worksheet_row(self, row):
        if not (row.get(self.TYPE_HEADER) and row.get(self.OLD_ID_HEADER) and row.get(self.NEW_ID_HEADER)):
            raise TransifexProjectMigrationInvalidUpload(_("missing value(s) in sheet"))
        if not row.get(self.TYPE_HEADER) in ['Menu', 'Form']:
            raise TransifexProjectMigrationInvalidUpload(
                _("Could not load file. 'Type' column should be either 'Menu' or 'Form'"))

    @memoized
    def uploaded_resource_id_mappings(self):
        uploaded_file = self.cleaned_data.get('mapping_file')
        worksheet = WorkbookJSONReader(uploaded_file).worksheets[0]
        self._validate_worksheet_headers(worksheet.headers)
        details = []
        for row in worksheet:
            self._validate_worksheet_row(row)
            details.append((row[self.TYPE_HEADER], row[self.OLD_ID_HEADER], row[self.NEW_ID_HEADER]))
        return details

    @cached_property
    def migrator(self):
        data = self.cleaned_data
        return ProjectMigrator(self.domain,
                               data['transifex_project_slug'],
                               self.cleaned_data['from_app_id'],
                               self.cleaned_data['to_app_id'],
                               self.uploaded_resource_id_mappings())

    def _invalid_apps(self):
        if self.cleaned_data['to_app_id'] == self.cleaned_data['from_app_id']:
            self.add_error('from_app_id', _("Source and target app can not be the same"))
            return True

    def _invalid_upload(self):
        try:
            self.uploaded_resource_id_mappings()
        except TransifexProjectMigrationInvalidUpload as e:
            self.add_error('mapping_file', e)
            return True

    def _validate_migration(self):
        try:
            self.migrator.validate()
        except InvalidProjectMigration as e:
            self.add_error(None, e)

    def clean(self):
        super(MigrateTransifexProjectForm, self).clean()
        if self._invalid_apps() or self._invalid_upload():
            return
        self._validate_migration()
