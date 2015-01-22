from django import forms
from django.utils.translation import ugettext_noop as _

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper

from corehq.apps.app_manager.models import get_apps_in_domain


class CreateNewReportBuilderForm(forms.Form):
    report_type = forms.ChoiceField(
        choices=[
            ('bar_chart', _("Bar Chart")),
            ('pie_chart', _("Pie Chart")),
            ('table', _("Table")),
        ],
    )

    application = forms.ChoiceField()
    source_type = forms.ChoiceField(choices=[
        ("case", _("Case")),
        ("form", _("Form")),
    ])
    report_source = forms.ChoiceField()

    def __init__(self, domain, *args, **kwargs):
        super(CreateNewReportBuilderForm, self).__init__(*args, **kwargs)

        apps = get_apps_in_domain(domain, full=True, include_remote=False)
        self.fields['application'].choices = [
            (app._id, app.name) for app in apps
        ]
        self.fields['report_source'].choices = [
            (ct, ct) for app in apps for ct in app.get_case_types()
        ] + [
            (form_id, form_id) for form_id in [
                form.get_unique_id() for app in apps for form in app.get_forms()
            ]
        ]

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = "report-builder-form"
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Create New Report'),
                'report_type',
                crispy.Field('application', data_bind='value: application'),
                crispy.Field('source_type', data_bind='value: sourceType'),
                crispy.Field('report_source', data_bind='options: caseTypeMap[application()][sourceType()]'),
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'create_new_report_builder_btn',
                        _('Next'),
                    )
                ),
            ),
        )


class ConfigureBarChartBuilderForm(forms.Form):
    report_name = forms.CharField()
    group_by = forms.ChoiceField()

    def __init__(self, domain, source_type, report_source, *args, **kwargs):
        super(ConfigureBarChartBuilderForm, self).__init__(*args, **kwargs)

        if source_type == 'case':
            self.fields['group_by'].choices = [
                # (cp, cp) for cp in # TODO - add case properties for the case here, will also need to know source type
            ]
        elif source_type == 'form':
            pass
        else:
            raise Exception('no valid source_type')

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Configure Bar Chart'),
                'report_name',
                'group_by',
            ),
            FormActions(
                crispy.ButtonHolder(
                    crispy.Submit(
                        'configure_bar_chart_builder_btn',
                        _('Save Bar Chart')
                    )
                ),
            ),
        )
