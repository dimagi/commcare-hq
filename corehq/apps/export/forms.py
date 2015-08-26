from django import forms
from django.utils.translation import ugettext as _

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms import layout as crispy

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain


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
