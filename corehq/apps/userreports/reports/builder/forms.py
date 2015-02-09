import json
import os
import uuid
from django import forms
from django.utils.translation import ugettext_noop as _

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper

from corehq.apps.app_manager.models import (
    Application,
    Form,
    get_apps_in_domain
)
from corehq.apps.app_manager.util import ParentCasePropertyBuilder
from corehq.apps.app_manager.xform import XForm
from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.reports.builder import make_case_property_indicator, \
    FORM_METADATA_PROPERTIES, DEFAULT_CASE_PROPERTY_DATATYPES
from dimagi.utils.decorators.memoized import memoized


class CreateNewReportForm(forms.Form):
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
        super(CreateNewReportForm, self).__init__(*args, **kwargs)

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

# TODO: Format types for the columns table don't make sense?
# TODO: Add some documentation


class ConfigureNewReportBase(forms.Form):
    report_name = forms.CharField()
    filters = forms.CharField()
    form_title = 'Configure Report'
    button_text = 'Save Report'

    def __init__(self, app_id, source_type, report_source_id, *args, **kwargs):
        super(ConfigureNewReportBase, self).__init__(*args, **kwargs)

        # Following attributes are needed for the create_report method
        assert source_type in ['case', 'form']
        self.source_type = source_type
        self.doc_type_map = {"case": "CommCareCase", "form": "XFormInstance"}
        self.report_source_id = report_source_id
        self.app = Application.get(app_id)
        self.domain = self.app.domain

        if self.source_type == "form":
            self.source_form = Form.get_form(self.report_source_id)
        elif self.source_type == "case":
            property_builder = ParentCasePropertyBuilder(
                self.app, DEFAULT_CASE_PROPERTY_DATATYPES.keys()
            )
            self.case_properties = list(
                property_builder.get_properties(self.report_source_id)
            )

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
            "..", "..", "templates", "userreports", "partials", "report_filter_configuration.html"
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

    def create_report(self):
        """
        Creates data source and report config.
        Returns report config id. #TODO: Does it?
        """

        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name="{} source".format(self.cleaned_data['report_name']),
            referenced_doc_type=self.doc_type_map[self.source_type],
            # The uuid gets truncated, so it's not really universally unique.
            table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
            configured_filter={
                'type': 'property_match',  # TODO - use boolean_expression
                'property_name': 'type',
                'property_value': self.report_source_id,
            },
            configured_indicators=self._data_source_indicators
        )
        # TODO: Does validate check for unique table ids? It should I think.
        data_source_config.validate()
        data_source_config.save()
        tasks.rebuild_indicators.delay(data_source_config._id)

        report = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config._id,
            title=self.cleaned_data['report_name'],
            aggregation_columns=self._report_aggregation_cols,
            columns=self._report_columns,
            filters=self._report_filters,
            configured_charts=self._report_charts
        )
        report.validate()
        report.save()
        return report

    @property
    def _report_aggregation_cols(self):
        return []

    @property
    def _report_columns(self):
        return []

    @property
    def _data_source_indicators(self):
        return []

    @property
    def _report_filters(self):
        '''
        Return the json filter configurations to be used by the
        ReportConfiguration that this form produces.
        '''

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
        return [_make_report_filter(f) for f in filter_configs]

    @property
    def _report_charts(self):
        return []

    @property
    @memoized
    def data_source_properties(self):
        '''
        Return dictionaries representing the various properties that may be
        present as indicators or columns in the data source or report.
        '''
        if self.source_type == 'case':
            return [{'id': cp, 'text': cp} for cp in self.case_properties]
        if self.source_type == 'form':
            xform = XForm(self.source_form.source)
            questions = xform.get_questions([])
            return [
                {
                    "type": "question",
                    "value": q,
                    "id": q['value'],
                    'text': q['label']
                } for q in questions
            ] + [
                {
                    "type": "meta",
                    "value": p[0],
                    'id': p[0],
                    'text': p[0]
                } for p in FORM_METADATA_PROPERTIES
            ]


class ConfigureNewBarChartReport(ConfigureNewReportBase):
    group_by = forms.ChoiceField()
    form_title = "Configure Bar Chart Report"

    def __init__(self, app_id, source_type, report_source_id, *args, **kwargs):
        super(ConfigureNewBarChartReport, self).__init__(app_id, source_type, report_source_id, *args, **kwargs)
        self.fields['group_by'].choices = self._group_by_choices

    # TODO: I don't love the name of this property...
    @property
    def top_fieldset(self):
        return crispy.Fieldset(
            _(self.form_title),
            'report_name',
            'group_by',
            self.configuration_tables
        )

    @property
    def _data_source_indicators(self):
        '''
        Return the json data source indicator configurations to be used by the
        DataSourceConfiguration used by the ReportConfiguration that this form
        produces.
        '''
        indicators = set(
            [f['field'] for f in self._report_filters] +
            [self.cleaned_data["group_by"]]
        )

        return [make_case_property_indicator(cp) for cp in indicators] + [
            {
                "display_name": "Count",
                "type": "count",
                "column_id": "count"
            }
        ]

    @property
    def _report_aggregation_cols(self):
        return [self.cleaned_data["group_by"]]

    @property
    def _report_charts(self):
        return [{
            "type": "multibar",
            "x_axis_column": self.cleaned_data["group_by"],
            "y_axis_columns": ["count"],
        }]

    @property
    def _report_columns(self):
        return [
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
        ]

    @property
    def _group_by_choices(self):
        return [(p['id'], p['text']) for p in self.data_source_properties]

# Should ConfigureNewBarChartReport and this class inherit from a
# common ancestor instead?
class ConfigureNewPieChartReport(ConfigureNewBarChartReport):
    form_title = "Configure Pie Chart Report"

    @property
    def _report_charts(self):
        return [{
            "type": "pie",
            "aggregation_column": self.cleaned_data["group_by"],
            "value_column": "count",
        }]


class ConfigureNewTableReport(ConfigureNewReportBase):
    form_title = "Configure Table Report"
    columns = forms.CharField(required=False)

    @property
    def configuration_tables(self):
        parent_tables = super(ConfigureNewTableReport, self).configuration_tables

        return crispy.Layout(
            parent_tables,
            crispy.Fieldset(
                _("Columns to Display"),
                crispy.Div(crispy.HTML(self.column_config_template), id="columns-table"),
                crispy.Hidden('columns', None, data_bind="value: serializedProperties")
            )
        )

    @property
    def _report_columns(self):
        def _make_column(conf):
            return {
                "format": "default",
                "aggregation": "simple",
                "field": conf['property'],
                "type": "field",
                "display": conf['display_text']
            }
        return [_make_column(conf) for conf in json.loads(self.cleaned_data['columns'])]

    @property
    def _data_source_indicators(self):
        property_name = set(
            [conf['property'] for conf in json.loads(self.cleaned_data['columns'])] +
            [f['field'] for f in self._report_filters]
        )
        return [make_case_property_indicator(p) for p in property_name]

    @property
    def _report_aggregation_cols(self):
        # TODO: Why is this needed?
        #       Does it aggregate on everything by default?
        return ['doc_id']
