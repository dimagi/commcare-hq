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
                crispy.Field('report_source', data_bind='''
                    options: sourcesMap[application()][sourceType()],
                    optionsText: function(item){return item.text},
                    optionsValue: function(item){return item.value}
                '''),
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

# TODO: implement create_report_from_form for table reports
# TODO: Make a pie report form
# TODO: Move the js from the templates into the forms
# TODO: Format types for the columns table don't make sense.
# TODO: Add some documentation

class ReportBuilderConfigureNewReportBase(forms.Form):
    report_name = forms.CharField()
    filters = forms.CharField()
    form_title = 'Configure Report'
    button_text = 'Save Report'

    def __init__(self, app_id, source_type, report_source, case_properties, *args, **kwargs):
        super(ReportBuilderConfigureNewReportBase, self).__init__(*args, **kwargs)

        # Following attributes are needed for the create_report_from_form method
        # TODO: Push these down to subclasses
        self.doc_type = source_type
        self.report_source = report_source
        self.case_properties = case_properties
        app = Application.get(app_id)
        self.domain = app.domain

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"

        self.helper.layout = crispy.Layout(
            self.top_fieldset,
            FormActions(
               crispy.ButtonHolder(
                   crispy.Submit(
                       'submit',
                       _(self.button_text)
                   )
               ),
            ),
        )

    @property
    def column_config_template(self):
        path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "templates", "userreports", "partials", "report_filter_configuration.html"
        )
        with open(path, "r") as f:
            template = f.read()
        return template

    @property
    def top_fieldset(self):
        return crispy.Fieldset(
            _(self.form_title),
            'report_name',
            self.configuration_tables
        )

    @property
    def configuration_tables(self):
        return crispy.Fieldset(
            _("Filters Available in this Report"),
            crispy.Div(crispy.HTML(self.column_config_template), id="filters-table"),
            crispy.Hidden('filters', None, data_bind="value: serializedProperties")
        )

    def create_report_from_form(self):
        raise NotImplementedError


class ReportBuilderConfigureNewBarChartReport(ReportBuilderConfigureNewReportBase):
    group_by = forms.ChoiceField()
    form_title = "Configure Bar Chart Report"

    def __init__(self, app_id, source_type, report_source, case_properties, *args, **kwargs):
        super(ReportBuilderConfigureNewBarChartReport, self).__init__(app_id, source_type, report_source, case_properties, *args, **kwargs)

        # Populate the group_by choices
        if source_type == 'case':
            self.fields['group_by'].choices = [
                (cp, cp) for cp in case_properties
            ]
        elif source_type == 'form':
            pass
        else:
            raise Exception('no valid source_type')

    @property
    def top_fieldset(self):
        return crispy.Fieldset(
            _(self.form_title),
            'report_name',
            'group_by',
            self.configuration_tables
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
            if conf['format'] == "Choice":
                filter["type"] = "dynamic_choice_list"
            elif conf['format'] == "Date":
                filter["type"] = "date"
            elif conf['format'] == "Numeric":
                filter["type"] = "numeric"
            else:
                # TODO: Raise something more specific or catch earlier
                raise Exception

            return filter

        filter_configs = json.loads(self.cleaned_data['filters'])
        indicators = set(
            [conf['property'] for conf in filter_configs] +
            [self.cleaned_data["group_by"]]
        )

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
                _make_indicator(cp) for cp in indicators
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
                _make_report_filter(f) for f in filter_configs
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


class ReportBuilderConfigureNewTableReport(ReportBuilderConfigureNewReportBase):
    form_title = "Configure Table Report"
    columns = forms.CharField(required=False)

    @property
    def configuration_tables(self):
        parent_tables = super(ReportBuilderConfigureNewTableReport, self).configuration_tables

        return crispy.Layout(
            parent_tables,
            crispy.Fieldset(
                _("Columns to Display"),
                crispy.Div(crispy.HTML(self.column_config_template), id="columns-table"),
                crispy.Hidden('columns', None, data_bind="value: serializedProperties")
            )
        )
