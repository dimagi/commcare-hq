import uuid
from django import forms
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.translation import ugettext_noop as _

from crispy_forms import layout as crispy
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper

from corehq.apps.app_manager.models import (
    Application,
    Form,
)
from corehq.apps.app_manager.util import ParentCasePropertyBuilder
from corehq.apps.app_manager.xform import XForm
from corehq.apps.userreports import tasks
from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.models import (
    DataSourceBuildInformation,
    DataSourceConfiguration,
    DataSourceMeta,
    ReportConfiguration,
    ReportMeta,
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
from corehq.apps.userreports.sql import get_column_name
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
                    prop['source'], prop['column_id']
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

        if self.source_type == 'case':
            return {
                cp: {
                    'type': 'case_property',
                    'id': cp,
                    'column_id': get_column_name(cp),
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
                    "column_id": get_column_name(q['value'].strip("/")),
                    'text': q['label'],
                    "source": q,
                } for q in questions
            })
            ret.update({
                p[0]: {
                    "type": "meta",
                    "id": p[0],
                    "column_id": get_column_name(p[0].strip("/")),
                    'text': p[0],
                    "source": p,
                } for p in FORM_METADATA_PROPERTIES
            })
            return ret

    @property
    @memoized
    def data_source_name(self):
        if self.source_type == 'form':
            return "{} (v{})".format(self.source_form.default_name(), self.app.version)
        if self.source_type == 'case':
            return "{} (v{})".format(self.source_id, self.app.version)

    def get_existing_match(self):
        return DataSourceConfiguration.view(
            'userreports/data_sources_by_build_info',
            key=[
                self.domain,
                self.source_doc_type,
                self.source_id,
                self.app._id,
                self.app.version
            ],
            reduce=False
        ).one()


class DataSourceForm(forms.Form):
    report_name = forms.CharField()
    chart_type = forms.ChoiceField(
        choices=[
            ('bar', _('Bar')),
            ('pie', _("Pie")),
        ],
    )

    def __init__(self, domain, report_type, *args, **kwargs):
        super(DataSourceForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.report_type = report_type

        self.app_source_helper = ApplicationDataSourceUIHelper()
        self.app_source_helper.bootstrap(self.domain)
        report_source_fields = self.app_source_helper.get_fields()
        self.fields.update(report_source_fields)

        self.fields['chart_type'].required = self.report_type == "chart"

        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.form_id = "report-builder-form"
        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('{} Report'.format(self.report_type.capitalize())),
                'report_name',
                'chart_type' if self.report_type == 'chart' else None
            ),
            crispy.Fieldset(
                _('Data'),
                *report_source_fields.keys()
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

    @property
    def sources_map(self):
        return self.app_source_helper.all_sources

    def get_selected_source(self):
        return self.app_source_helper.get_app_source(self.cleaned_data)

    def clean(self):
        """
        Raise a validation error if there are already 5 data sources and this
        report won't be able to use one of the existing ones.
        """
        cleaned_data = super(DataSourceForm, self).clean()
        source_type = cleaned_data.get('source_type')
        report_source = cleaned_data.get('report_source')
        app_id = cleaned_data.get('application')

        if report_source and source_type and app_id:

            app = Application.get(app_id)
            ds_builder = DataSourceBuilder(self.domain, app, source_type, report_source)

            existing_sources = DataSourceConfiguration.by_domain(self.domain)
            if len(existing_sources) >= 5:
                if not ds_builder.get_existing_match():
                    raise forms.ValidationError(_(
                        "Too many data sources!\n"
                        "Creating this report would cause you to go over the maximum "
                        "number of data sources allowed in this domain. The current "
                        "limit is 5. "
                        "To continue, delete all of the reports using a particular "
                        "data source (or the data source itself) and try again. "
                    ))

        return cleaned_data


class ConfigureNewReportBase(forms.Form):
    filters = FilterField(required=False)
    button_text = 'Done'

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        """
        This form can be used to create a new ReportConfiguration, or to modify
        an existing one if existing_report is set.
        """
        super(ConfigureNewReportBase, self).__init__(*args, **kwargs)
        self.existing_report = existing_report

        if self.existing_report:
            self._bootstrap(self.existing_report)
            self.button_text = _('Update Report')
        else:
            self.report_name = report_name
            assert source_type in ['case', 'form']
            self.source_type = source_type
            self.report_source_id = report_source_id
            self.app = Application.get(app_id)

        self.domain = self.app.domain
        self.ds_builder = DataSourceBuilder(
            self.domain, self.app, self.source_type, self.report_source_id
        )
        self.data_source_properties = self.ds_builder.data_source_properties
        self._properties_by_column = {
            p['column_id']: p for p in self.data_source_properties.values()
        }

        # NOTE: The corresponding knockout view model is defined in:
        #       templates/userreports/partials/report_builder_configure_report.html
        self.helper = FormHelper()
        self.helper.form_class = "form-horizontal"
        self.helper.attrs['data_bind'] = "submit: submitHandler"
        self.helper.form_id = "report-config-form"

        buttons = [crispy.Submit('submit', _(self.button_text))]
        # Add a back button if we aren't editing an existing report
        if not self.existing_report:
            buttons.insert(
                0,
                crispy.HTML(
                    '<a class="btn" href="{}" style="margin-right: 4px">{}</a>'.format(
                        reverse(
                            'report_builder_select_source',
                            args=(self.domain, self.report_type),
                        ),
                        _('Back')
                    )
                ),
            )
        # Add a "delete report" button if we are editing an existing report
        else:
            buttons.insert(
                0,
                crispy.HTML(
                    '<a class="btn btn-danger" href="{}" style="margin-right: 4px">{}</a>'.format(
                        reverse('delete_configurable_report', args=(self.domain, self.existing_report._id)),
                        _('Delete Report')
                    )
                )
            )
        self.helper.layout = crispy.Layout(
            self.container_fieldset,
            FormActions(crispy.ButtonHolder(*buttons)),
        )

    def _bootstrap(self, existing_report):
        """
        Use an existing report to initialize some of the instance variables of this
        form. This method is used when editing an existing report.
        """
        self.report_name = existing_report.title
        self.source_type = {
            "CommCareCase": "case",
            "XFormInstance": "form"
        }[existing_report.config.referenced_doc_type]
        self.report_source_id = existing_report.config.meta.build.source_id
        self.app = Application.get(existing_report.config.meta.build.app_id)

    @property
    def column_config_template(self):
        return render_to_string('userreports/partials/report_filter_configuration.html')

    @property
    def container_fieldset(self):
        """
        Return the first fieldset in the form.
        """
        return crispy.Fieldset(
            "",
            self.filter_fieldset
        )

    @property
    def filter_fieldset(self):
        """
        Return a fieldset representing the markup used for configuring the
        report filters.
        """
        return crispy.Fieldset(
            _("Filters"),
            crispy.Div(
                crispy.HTML(self.column_config_template), id="filters-table", data_bind='with: filtersList'
            ),
            crispy.Hidden('filters', None, data_bind="value: filtersList.serializedProperties")
        )

    def update_report(self):
        self.existing_report.aggregation_columns = self._report_aggregation_cols
        self.existing_report.columns = self._report_columns
        self.existing_report.filters = self._report_filters
        self.existing_report.configured_charts = self._report_charts
        self.existing_report.validate()
        self.existing_report.save()
        return self.existing_report

    def create_report(self):
        """
        Creates data source and report config.
        """
        matching_data_source = self.ds_builder.get_existing_match()
        if matching_data_source:
            data_source_config_id = matching_data_source['id']
        else:
            data_source_config = DataSourceConfiguration(
                domain=self.domain,
                display_name=self.ds_builder.data_source_name,
                referenced_doc_type=self.ds_builder.source_doc_type,
                # The uuid gets truncated, so it's not really universally unique.
                table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
                configured_filter=self.ds_builder.filter,
                configured_indicators=self.ds_builder.indicators,
                meta=DataSourceMeta(build=DataSourceBuildInformation(
                    source_id=self.report_source_id,
                    app_id=self.app._id,
                    app_version=self.app.version,
                ))
            )
            data_source_config.validate()
            data_source_config.save()
            tasks.rebuild_indicators.delay(data_source_config._id)
            data_source_config_id = data_source_config._id

        report = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config_id,
            title=self.report_name,
            aggregation_columns=self._report_aggregation_cols,
            columns=self._report_columns,
            filters=self._report_filters,
            configured_charts=self._report_charts,
            report_meta=ReportMeta(
                created_by_builder=True,
                builder_report_type=self.report_type
            )
        )
        report.validate()
        report.save()
        return report

    @property
    @memoized
    def initial_filters(self):
        if self.existing_report:
            return [self._get_view_model(f) for f in self.existing_report.filters]
        if self.source_type == 'case':
            return [
                {'property': 'closed', 'display_text': 'closed', 'format': 'Choice'},
                # TODO: Allow users to filter by owner name, not just id.
                # This will likely require implementing data source filters.
                {'property': 'owner_id', 'display_text': 'owner id', 'format': 'Choice'},
            ]
        else:
            # self.source_type == 'form'
            return [
                {'property': 'timeEnd', 'display_text': 'Form completion time', 'format': 'Date'}
            ]

    def _get_view_model(self, filter):
        """
        Given a ReportFilter, return a dictionary representing the knockout view
        model representing this filter in the report builder.
        """
        filter_type_map = {
            'dynamic_choice_list': 'Choice',
            'choice_list': 'Choice',  # This exists to handle the `closed` filter that might exist
            'date': 'Date',
            'numeric': 'Numeric'
        }
        return {
            'property': self._get_property_from_column(filter['field']),
            'display_text': filter['display'],
            'format': filter_type_map[filter['type']]
        }

    def _get_property_from_column(self, col):
        return self._properties_by_column[col]['id']

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']

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
        filters = [_make_report_filter(f) for f in filter_configs]
        if self.source_type == 'case':
            # The UI doesn't support specifying "choice_list" filters, only "dynamic_choice_list" filters.
            # But, we want to make the open/closed filter a cleaner "choice_list" filter, so we do that here.
            self._convert_closed_filter_to_choice_list(filters)
        return filters

    @classmethod
    def _convert_closed_filter_to_choice_list(cls, filters):
        for f in filters:
            if f['field'] == get_column_name('closed') and f['type'] == 'dynamic_choice_list':
                f['type'] = 'choice_list'
                f['choices'] = [
                    {'value': 'True'},
                    {'value': 'False'}
                ]

    @property
    def _report_charts(self):
        return []


class ConfigureBarChartReportForm(ConfigureNewReportBase):
    group_by = forms.ChoiceField(label="Property")
    report_type = 'chart'

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        super(ConfigureBarChartReportForm, self).__init__(
            report_name, app_id, source_type, report_source_id, existing_report, *args, **kwargs
        )
        self.fields['group_by'].choices = self._group_by_choices

        # Set initial value of group_by
        if self.existing_report:
            existing_agg_cols = existing_report.aggregation_columns
            assert len(existing_agg_cols) < 2
            if existing_agg_cols:
                self.fields['group_by'].initial = self._get_property_from_column(existing_agg_cols[0])

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            _('Categories'),
            'group_by',
            self.filter_fieldset
        )

    @property
    def aggregation_field(self):
        return self.cleaned_data["group_by"]

    @property
    def _report_aggregation_cols(self):
        return [
            self.data_source_properties[self.aggregation_field]['column_id']
        ]

    @property
    def _report_charts(self):
        agg_col = self.data_source_properties[self.aggregation_field]['column_id']
        return [{
            "type": "multibar",
            "x_axis_column": agg_col,
            "y_axis_columns": ["count"],
        }]

    @property
    def _report_columns(self):
        agg_col_id = self.data_source_properties[self.aggregation_field]['column_id']
        agg_disp = self.data_source_properties[self.aggregation_field]['text']
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


class ConfigurePieChartReportForm(ConfigureBarChartReportForm):

    @property
    def _report_charts(self):
        agg = self.data_source_properties[self.aggregation_field]['column_id']
        return [{
            "type": "pie",
            "aggregation_column": agg,
            "value_column": "count",
        }]


class ConfigureListReportForm(ConfigureNewReportBase):
    report_type = 'list'
    columns = JsonField(required=True)

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            "",
            self.column_fieldset,
            self.filter_fieldset
        )

    @property
    def column_fieldset(self):
        return crispy.Fieldset(
            _("Columns"),
            crispy.Div(
                crispy.HTML(self.column_config_template), id="columns-table", data_bind='with: columnsList'
            ),
            crispy.Hidden('columns', None, data_bind="value: columnsList.serializedProperties")
        )

    @property
    @memoized
    def initial_columns(self):
        if self.existing_report:
            cols = []
            for c in self.existing_report.columns:
                cols.append({
                    'property': self._get_property_from_column(c['field']),
                    'display_text': c['display']
                })
            return cols
        return []

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


class ConfigureTableReportForm(ConfigureListReportForm, ConfigureBarChartReportForm):
    report_type = 'table'

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            "",
            self.column_fieldset,
            crispy.Fieldset(
                _('Rows'),
                'group_by',
            ),
            self.filter_fieldset
        )

    @property
    def _report_charts(self):
        # Override the behavior inherited from ConfigureBarChartReportForm
        return []

    @property
    def _report_columns(self):
        agg_col_id = self.data_source_properties[self.aggregation_field]['column_id']

        columns = super(ConfigureTableReportForm, self)._report_columns
        # Expand all columns except for the column being used for aggregation.
        for c in columns:
            if c['field'] != agg_col_id:
                c['aggregation'] = "expand"
        return columns

    @property
    @memoized
    def _report_aggregation_cols(self):
        # we want the bar chart behavior, which is reproduced here:
        return [
            self.data_source_properties[self.aggregation_field]['column_id']
        ]


class ConfigureWorkerReportForm(ConfigureTableReportForm):
    # This is a ConfigureTableReportForm, but with a predetermined aggregation
    report_type = 'worker'

    def __init__(self, *args, **kwargs):
        super(ConfigureWorkerReportForm, self).__init__(*args, **kwargs)
        self.fields.pop('group_by')

    @property
    def aggregation_field(self):
        if self.source_type == "form":
            return "username"
        if self.source_type == "case":
            return "user_id"

    @property
    def container_fieldset(self):
        return crispy.Fieldset(
            "",
            self.column_fieldset,
            self.filter_fieldset
        )
