import json
from django import forms
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.hqwebapp.crispy import BootstrapMultiField
from corehq.apps.style.crispy import B3MultiField, CrispyTemplate
from corehq.apps.style.forms.widgets import Select2MultipleChoiceWidget, \
    DateRangePickerWidget

from crispy_forms.bootstrap import FormActions, InlineField
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from crispy_forms.layout import Layout, Fieldset


class CreateFormExportForm(forms.Form):
    application = forms.ChoiceField()
    module = forms.ChoiceField()
    form = forms.ChoiceField()

    def __init__(self, domain, *args, **kwargs):
        super(CreateFormExportForm, self).__init__(*args, **kwargs)
        apps = get_apps_in_domain(domain)
        self.fields['application'].choices = ([
            ('', _('Select Application...')),
        ] if len(apps) > 1 else []) + [
            (app._id, app.name) for app in apps
        ]
        self.fields['module'].choices = [
            (module.unique_id, module.name)
            for app in apps if hasattr(app, 'modules')
            for module in app.modules
        ]
        self.fields['form'].choices = [
            (form.get_unique_id(), form.name)
            for app in apps
            for form in app.get_forms()
        ]

        self.helper = FormHelper()
        self.helper.form_id = "create-export-form"
        self.helper.form_class = "form-horizontal"

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Select Form'),
                crispy.Field(
                    'application',
                    data_bind='value: appId',
                ),
                crispy.Div(
                    crispy.Field(
                        'module',
                        data_bind=(
                            "options: moduleOptions, "
                            "optionsText: 'text', "
                            "optionsValue: 'value', "
                            "value: moduleId"
                        ),
                    ),
                    data_bind="visible: appId",
                ),
                crispy.Div(
                    crispy.Field(
                        'form',
                        data_bind=(
                            "options: formOptions, "
                            "optionsText: 'text', "
                            "optionsValue: 'value', "
                            "value: formId"
                        ),
                    ),
                    data_bind="visible: moduleId",
                ),
            ),
            crispy.Div(
                FormActions(
                    crispy.ButtonHolder(
                        crispy.Submit(
                            'create_export',
                            _('Next'),
                        ),
                    ),
                ),
                data_bind="visible: formId",
            ),
        )


class CreateCaseExportForm(forms.Form):
    application = forms.ChoiceField()
    case_type = forms.ChoiceField()

    def __init__(self, domain, *args, **kwargs):
        super(CreateCaseExportForm, self).__init__(*args, **kwargs)
        apps = get_apps_in_domain(domain)
        self.fields['application'].choices = ([
            ('', _('Select Application...')),
        ] if len(apps) > 1 else []) + [
            (app._id, app.name) for app in apps
        ]
        self.fields['case_type'].choices = [
            (module.case_type, module.case_type)
            for app in apps if hasattr(app, 'modules')
            for module in app.modules
            if module.case_type
        ]

        self.helper = FormHelper()
        self.helper.form_id = "create-export-form"
        self.helper.form_class = "form-horizontal"

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Select Case Type'),
                crispy.Field(
                    'application',
                    data_bind='value: appId',
                ),
                crispy.Div(
                    crispy.Field(
                        'case_type',
                        data_bind=(
                            "options: caseTypeOptions, "
                            "optionsText: 'text', "
                            "optionsValue: 'value', "
                            "value: case_type"
                        ),
                    ),
                    data_bind="visible: appId",
                ),
            ),
            crispy.Div(
                FormActions(
                    crispy.ButtonHolder(
                        crispy.Submit(
                            'create_export',
                            _('Next'),
                        ),
                    ),
                ),
                data_bind="visible: case_type",
            ),
        )

_USER_TYPES_CHOICES = [
    ('mobile', ugettext_noop("Mobile Worker")),
    ('demo_user', ugettext_noop("Demo User")),
    ('admin', ugettext_noop("Admin")),
    ('unknown', ugettext_noop("Unknown")),
    ('supply', ugettext_noop("CommCare Supply")),
]


class FilterExportDownloadForm(forms.Form):

    user_types = forms.MultipleChoiceField(
        label=ugettext_noop("User Type"),
        required=True,
        choices=_USER_TYPES_CHOICES,
        widget=Select2MultipleChoiceWidget
    )
    groups = forms.MultipleChoiceField(
        label=ugettext_noop("Groups"),
        required=False,
        choices=[],  # filled dynamically
        widget=Select2MultipleChoiceWidget,
    )
    date_range = forms.CharField(
        label=ugettext_noop("Date Range"),
        required=True,
        widget=DateRangePickerWidget(),
    )
    exports = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
    )

    def __init__(self, domain, timezone, *args, **kwargs):
        self.domain = domain
        self.timezone = timezone
        super(FilterExportDownloadForm, self).__init__(*args, **kwargs)
        self.fields['date_range'].help_text = _(
            "The timezone for this export is %(timezone)s."
        ) % {
            'timezone': self.timezone,
        }

        initial = kwargs.get('initial', {})
        if initial.get('export_id'):
            self.fields['export_id'].widget = forms.HiddenInput()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.label_class = 'col-sm-2'
        self.helper.field_class = 'col-sm-5'
        self.helper.layout = Layout(
            crispy.Field(
                'export_id',
                ng_required='true',
                ng_model='formData.export_id',
            ),
            crispy.Field(
                'user_types',
                ng_model='formData.user_types',
                ng_required='true',
                placeholder=_("Everyone"),
                ng_init="formData.user_types = [{}]".format(
                    json.dumps(_USER_TYPES_CHOICES[0])
                )
            ),
            B3MultiField(
                _("Groups"),
                crispy.Div(
                    crispy.Div(
                        InlineField(
                            'groups',
                            ng_model='formData.groups',
                            ng_required='false',
                            style="width: 98%",
                        ),
                        ng_show="showSelectGroups && hasGroups",
                    ),
                ),
                CrispyTemplate('export/crispy_html/groups_help.html', {
                    'domain': self.domain,
                }),
            ),
            crispy.Field(
                'date_range',
                ng_model='formData.date_rage',
                ng_required='true',
            ),
        )

    def format_form_export(self, export):
        return {
            'export_id': export.get_id,
            'xmlns': export.xmlns if hasattr(export, 'xmlns') else '',
            'export_type': 'form',
            'format':  export.default_format,
            'dlocation': reverse('export_custom_data',
                                 args=[self.domain, export.get_id]),
            'name': export.name,
        }
