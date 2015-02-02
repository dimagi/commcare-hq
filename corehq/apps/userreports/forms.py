import json
import os
from django import forms
from django.utils.translation import ugettext_noop as _

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper

from corehq.apps.app_manager.models import (
    Application,
    get_apps_in_domain,
)
from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager import (
    get_default_case_property_datatypes,
    _clean_table_name,
)
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)


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
                crispy.Field('report_source', data_bind='options: sourcesMap[application()][sourceType()]'),
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
    filters = forms.CharField(required=False)

    def __init__(self, app_id, source_type, report_source, case_properties, *args, **kwargs):
        super(ConfigureBarChartBuilderForm, self).__init__(*args, **kwargs)

        self.doc_type = source_type
        self.report_source = report_source
        self.case_properties = case_properties
        app = Application.get(app_id)
        self.domain = app.domain
        if source_type == 'case':
            self.fields['group_by'].choices = [
                (cp, cp) for cp in case_properties
            ]
        elif source_type == 'form':
            pass
        else:
            raise Exception('no valid source_type')

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"

        # TODO: This is almost certainly the wrong way to get this template
        path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "templates", "userreports", "partials", "report_filter_configuration.html"
        )
        with open(path, "r") as f:
            template = f.read()

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Configure Bar Chart'),
                'report_name',
                'group_by',
                crispy.Fieldset(
                    _("Filters Available in this Report"),
                    crispy.HTML(template),
                ),
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

    def create_report_from_form(self):
        """
        Creates data source and report config.
        Returns report config id.
        """
        default_case_property_datatypes = get_default_case_property_datatypes()

        def _make_indicator(property_name):
            return {
                "type": "raw",
                "column_id": property_name,
                "datatype": default_case_property_datatypes.get(property_name, "string"),
                'property_name': property_name,
                "display_name": property_name,
            }

        def _make_report_filter(conf):
            filter = {
                "field": conf["property"],
                "slug": conf["property"],
                "display": conf["display_text"]
            }
            if conf['format'] == "Plain":
                filter["type"] = "dynamic_choice_list"
            elif conf['format'] == "Date":
                filter["type"] = "date"
            else:
                # TODO: Raise something more specific or catch earlier
                raise Exception

            return filter

        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name="{} source".format(self.cleaned_data['report_name']),
            referenced_doc_type=self.doc_type,
            table_id=_clean_table_name(self.domain, self.report_source),
            configured_filter={
                'type': 'property_match',  # TODO - use boolean_expression
                'property_name': 'type',
                'property_value': self.report_source,
            },
            configured_indicators=[
                _make_indicator(cp) for cp in self.case_properties
            ]+[
                {
                    "display_name": "Count",
                    "type": "count",
                    "column_id": "count"
                }
            ],
        )
        data_source_config.save()
        tasks.rebuild_indicators.delay(data_source_config._id)

        report = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config._id,
            title=self.cleaned_data['report_name'],
            aggregation_columns=[self.cleaned_data["group_by"]],
            columns=[
                {
                    "format": "default",
                    "aggregation": "simple",
                    "field": self.cleaned_data["group_by"],
                    "type": "field",
                    "display": self.cleaned_data["group_by"]
                },
                {
                    "format": "default",
                    "aggregation": "sum",
                    "field": "count",
                    "type": "field",
                    "display": "Count"
                }
            ],
            filters=[
                _make_report_filter(f) for f in json.loads(self.cleaned_data['filters'])
            ],
            configured_charts=[{
                "type": "multibar",
                "x_axis_column": self.cleaned_data["group_by"],
                "y_axis_columns": ["count"],

            }]
        )
        report.validate()
        report.save()
        return report
