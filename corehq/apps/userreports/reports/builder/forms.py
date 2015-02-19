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
from corehq.apps.userreports.reports.builder import (
    DEFAULT_CASE_PROPERTY_DATATYPES,
    FORM_METADATA_PROPERTIES,
    make_case_data_source_filter,
    make_case_property_indicator,
    make_form_data_source_filter,
    make_form_meta_block_indicator,
    make_form_question_indicator,
)
from corehq.apps.userreports.ui.fields import JsonField
from dimagi.utils.decorators.memoized import memoized


class FilterField(JsonField):
    """
    A form field with a little bit of validation for report builder report
    filter configuration.
    """
    def validate(self, value):
        super(FilterField, self).validate(value)
        for filter_conf in value:
            if filter_conf.get('format', None) not in ['Choice', 'Date', 'Numeric']:
                raise forms.ValidationError("Invalid filter format!")


# NOTE: Should I break this into two classes, one for forms and one for cases?
class DataSourceBuilder(object):
    """
    When configuring a report, one can use DataSourceBuilder to determine some
    of the properties of the required report data source, such as:
        - referenced doc type
        - filter
        - indicators
    """

    def __init__(self, domain, app, source_type, source_id):
        assert (source_type in ['case', 'form'])

        self.domain = domain
        self.app = app
        self.source_type = source_type
        # source_id is a case type of form id
        self.source_id = source_id
        if self.source_type == 'form':
            self.source_form = Form.get_form(self.source_id)
            self.source_xform = XForm(self.source_form.source)
        if self.source_type == 'case':
            property_builder = ParentCasePropertyBuilder(
                self.app, DEFAULT_CASE_PROPERTY_DATATYPES.keys()
            )
            self.case_properties = list(
                property_builder.get_properties(self.source_id) | {'closed'}
            )

    @property
    @memoized
    def source_doc_type(self):
        if self.source_type == "case":
            return "CommCareCase"
        if self.source_type == "form":
            return "XFormInstance"

    @property
    @memoized
    def filter(self):
        """
        Return the filter configuration for the DataSourceConfiguration.
        """
        if self.source_type == "case":
            return make_case_data_source_filter(self.source_id)
        if self.source_type == "form":
            return make_form_data_source_filter(self.source_xform.data_node.tag_xmlns)

    @property
    @memoized
    def indicators(self):
        """
        Return all the dict data source indicator configurations that could be
        used by a report that uses the same case type/form as this DataSourceConfiguration.
        """
        ret = []
        for prop in self.data_source_properties.values():
            if prop['type'] == 'meta':
                ret.append(make_form_meta_block_indicator(
                    prop['source'][0], prop['source'][1]
                ))
            elif prop['type'] == "question":
                ret.append(make_form_question_indicator(
                    prop['source'], prop['column_id']
                ))
            elif prop['type'] == 'case_property':
                ret.append(make_case_property_indicator(
                    prop['source'], prop['column_id']
                ))
        ret.append({
            "display_name": "Count",
            "type": "count",
            "column_id": "count"
        })
        return ret

    @property
    @memoized
    def data_source_properties(self):
        """
        A dictionary containing the various properties that may be used as indicators
        or columns in the data source or report.

        Keys are strings that uniquely identify properties.
        Values are dicts representing the properties, ex:

        >> self.data_source_properties
        {
            "/data/question1": {
                "type": "question",
                "id": "/data/question1",
                "text": "Enter the child's name",
                "column_id": "data--question1",
                "source": {
                    'repeat': None,
                    'group': None,
                    'value': '/data/question1',
                    'label': 'question1',
                    'tag': 'input',
                    'type': 'Text'
                }
            },
            "meta/deviceID": {
                "type": "meta",
                "id": "meta/deviceID",
                "text": "deviceID",
                "column_id": "meta--deviceID",
                "source": ("deviceID", "string")
            }
        }

        "id" is used as the value in selects/select2s in the form. Uniquely identifies questions.
        "column_id" is used as the column name for this indicator. There are bugs
        with slashes which requires this to be different from "id"
        "text" will be used as the visible text in selects/select2s
        "type" is "question", "case_property", or "meta"
        For questions, "source" is the dict returned by Xform.get_questions, for
        case properties and form metadata it is simply the name of the property.
        """

        def escape_id(id):
            # TODO: This is fairly naive escaping
            return id.strip("/").replace("/", "__")

        if self.source_type == 'case':
            return {
                cp: {
                    'type': 'case_property',
                    'id': cp,
                    'column_id': escape_id(cp),
                    'text': cp,
                    'source': cp
                } for cp in self.case_properties
            }

        if self.source_type == 'form':
            ret = {}
            questions = self.source_xform.get_questions([])
            ret.update({
                q['value']: {
                    "type": "question",
                    "id": q['value'],
                    "column_id": escape_id(q['value']),
                    'text': q['label'],
                    "source": q,
                } for q in questions
            })
            ret.update({
                p[0]: {
                    "type": "meta",
                    "id": p[0],
                    "column_id": escape_id(p[0]),
                    'text': p[0],
                    "source": p,
                } for p in FORM_METADATA_PROPERTIES
            })
            return ret


class CreateNewReportForm(forms.Form):
    """
    A form for the first page of the report builder.
    Allows user to specify report type, application, and source.
    """
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

        self.domain = domain
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

    def clean(self):
        """
        Raise a validation error if there are already 5 data sources and this
        report won't be able to use one of the existing ones.
        """
        cleaned_data = super(CreateNewReportForm, self).clean()
        source_type = cleaned_data.get('source_type')
        report_source = cleaned_data.get('report_source')
        app_id = cleaned_data.get('application')

        if report_source and source_type and app_id:
            app = Application.get(app_id)
            ds_builder = DataSourceBuilder(self.domain, app, source_type, report_source)

            existing_sources = DataSourceConfiguration.by_domain(self.domain)
            if len(existing_sources) >= 5:
                suitable_source_exists = False
                for s in existing_sources:
                    if (
                        s.referenced_doc_type == ds_builder.source_doc_type and
                        s.configured_filter == ds_builder.filter and
                        s.configured_indicators == ds_builder.indicators
                    ):
                        suitable_source_exists = True
                        break
                if not suitable_source_exists:
                    raise forms.ValidationError(_(
                        "Too many data sources!\n"
                        "Creating this report would cause you to go over the maximum "
                        "number of data sources allowed in this domain. The current "
                        "limit is 5. Each case type and form that you have a user "
                        "configurable report for count towards your limit. To continue, "
                        "delete all the reports using a particular data source (or "
                        "the data source itself) and try again."
                    ))

        return cleaned_data


class ConfigureNewReportBase(forms.Form):
    report_name = forms.CharField()
    filters = FilterField()
    form_title = 'Configure Report'
    button_text = 'Save Report'

    def __init__(self, app_id, source_type, report_source_id, *args, **kwargs):
        super(ConfigureNewReportBase, self).__init__(*args, **kwargs)

        assert source_type in ['case', 'form']
        self.source_type = source_type
        self.report_source_id = report_source_id
        self.app = Application.get(app_id)
        self.domain = self.app.domain

        self.ds_builder = DataSourceBuilder(
            self.domain, self.app, self.source_type, self.report_source_id
        )
        self.data_source_properties = self.ds_builder.data_source_properties

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.attrs['data_bind'] = "submit: submitHandler"
        self.helper.form_id = "report-config-form"

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

    # TODO: I don't love the name of this property...
    @property
    def top_fieldset(self):
        """
        Return the first fieldset in the form.
        """
        return crispy.Fieldset(
            _(self.form_title),
            'report_name',
            self.configuration_tables
        )

    @property
    def configuration_tables(self):
        """
        Return a fieldset representing the markup used for configuring the
        report filters.
        """
        return crispy.Fieldset(
            _("Filters Available in this Report"),
            crispy.Div(
                crispy.HTML(self.column_config_template), id="filters-table", data_bind='with: filtersList'
            ),
            crispy.Hidden('filters', None, data_bind="value: filtersList.serializedProperties")
        )

    def create_report(self):
        """
        Creates data source and report config.
        """
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name="{} source".format(self.cleaned_data['report_name']),
            referenced_doc_type=self.ds_builder.source_doc_type,
            # The uuid gets truncated, so it's not really universally unique.
            table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
            configured_filter=self.ds_builder.filter,
            configured_indicators=self.ds_builder.indicators
        )
        data_source_config.validate()

        # Check if a suitable data source already exists.
        # This checking is pretty naive. Do something better.
        # Also inefficient. Consider writing a new couch view.
        sources = DataSourceConfiguration.by_domain(self.domain)
        match = None
        for s in sources:
            if (
                s.referenced_doc_type == data_source_config.referenced_doc_type and
                s.configured_filter == data_source_config.configured_filter and
                s.configured_indicators == data_source_config.configured_indicators
            ):
                match = s
                break
        if not match:
            data_source_config.save()
            tasks.rebuild_indicators.delay(data_source_config._id)
        else:
            data_source_config = match

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
    def _report_filters(self):
        """
        Return the dict filter configurations to be used by the
        ReportConfiguration that this form produces.
        """
        filter_type_map = {
            'Choice': 'dynamic_choice_list',
            'Date': 'date',
            'Numeric': 'numeric'
        }

        def _make_report_filter(conf):
            col_id = self.data_source_properties[conf["property"]]['column_id']
            return {
                "field": col_id,
                "slug": col_id,
                "display": conf["display_text"],
                "type": filter_type_map[conf['format']]
            }

        filter_configs = self.cleaned_data['filters']
        return [_make_report_filter(f) for f in filter_configs]

    @property
    def _report_charts(self):
        return []


class ConfigureNewBarChartReport(ConfigureNewReportBase):
    group_by = forms.ChoiceField()
    form_title = "Configure Bar Chart Report"

    def __init__(self, app_id, source_type, report_source_id, *args, **kwargs):
        super(ConfigureNewBarChartReport, self).__init__(app_id, source_type, report_source_id, *args, **kwargs)
        self.fields['group_by'].choices = self._group_by_choices

    @property
    def top_fieldset(self):
        return crispy.Fieldset(
            _(self.form_title),
            'report_name',
            'group_by',
            self.configuration_tables
        )

    @property
    def _report_aggregation_cols(self):
        agg = self.cleaned_data["group_by"]
        return [
            self.data_source_properties[agg]['column_id']
        ]

    @property
    def _report_charts(self):
        agg_col = self.data_source_properties[self.cleaned_data["group_by"]]['column_id']
        return [{
            "type": "multibar",
            "x_axis_column": agg_col,
            "y_axis_columns": ["count"],
        }]

    @property
    def _report_columns(self):
        agg_id = self.cleaned_data["group_by"]
        agg_col_id = self.data_source_properties[agg_id]['column_id']
        agg_disp = self.data_source_properties[agg_id]['text']
        return [
            {
                "format": "default",
                "aggregation": "simple",
                "field": agg_col_id,
                "type": "field",
                "display": agg_disp
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
        return [(p['id'], p['text']) for p in self.data_source_properties.values()]


class ConfigureNewPieChartReport(ConfigureNewBarChartReport):
    form_title = "Configure Pie Chart Report"

    @property
    def _report_charts(self):
        agg = self.data_source_properties[self.cleaned_data["group_by"]]['column_id']
        return [{
            "type": "pie",
            "aggregation_column": agg,
            "value_column": "count",
        }]


class ConfigureNewTableReport(ConfigureNewReportBase):
    form_title = "Configure Table Report"
    columns = JsonField(required=False)

    @property
    def configuration_tables(self):
        parent_tables = super(ConfigureNewTableReport, self).configuration_tables

        return crispy.Layout(
            parent_tables,
            crispy.Fieldset(
                _("Columns to Display"),
                crispy.Div(
                    crispy.HTML(self.column_config_template), id="columns-table", data_bind='with: columnsList'
                ),
                crispy.Hidden('columns', None, data_bind="value: columnsList.serializedProperties")
            )
        )

    @property
    def _report_columns(self):
        def _make_column(conf):
            return {
                "format": "default",
                "aggregation": "simple",
                "field": self.data_source_properties[conf['property']]['column_id'],
                "type": "field",
                "display": conf['display_text']
            }
        return [_make_column(conf) for conf in self.cleaned_data['columns']]

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']
