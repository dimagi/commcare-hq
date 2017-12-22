from __future__ import absolute_import
from collections import namedtuple, OrderedDict
from itertools import chain
import json
import uuid
from django.conf import settings
from django import forms
from django.forms import Widget
from django.forms.utils import flatatt
from django.template.loader import render_to_string
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.apps.app_manager.app_schemas.case_properties import get_case_properties

from corehq.apps.userreports.reports.builder.columns import (
    QuestionColumnOption,
    CountColumn,
    MultiselectQuestionColumnOption,
    FormMetaColumnOption,
    OwnernameComputedCasePropertyOption,
    UsernameComputedCasePropertyOption,
    CasePropertyColumnOption,
)
from crispy_forms import layout as crispy
from crispy_forms.bootstrap import StrictButton
from crispy_forms.helper import FormHelper
from corehq.apps.hqwebapp import crispy as hqcrispy

from corehq.apps.app_manager.fields import ApplicationDataSourceUIHelper
from corehq.apps.app_manager.models import (
    Application,
    Form,
)
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
    make_form_data_source_filter,
    get_filter_format_from_question_type,
)
from corehq.apps.userreports.exceptions import BadBuilderConfigError
from corehq.apps.userreports.reports.builder.const import COMPUTED_USER_NAME_PROPERTY_ID, \
    COMPUTED_OWNER_NAME_PROPERTY_ID, PROPERTY_TYPE_QUESTION, PROPERTY_TYPE_CASE_PROP, PROPERTY_TYPE_META, \
    AGGREGATION_COUNT_PER_CHOICE, AGGREGATION_SUM, AGGREGATION_SIMPLE, AGGREGATION_GROUP_BY, AGGREGATION_AVERAGE, \
    UCR_REPORT_AGGREGATION_AVG, UCR_REPORT_AGGREGATION_EXPAND, UCR_REPORT_AGGREGATION_SIMPLE, UCR_REPORT_AGGREGATION_SUM
from corehq.apps.userreports.sql import get_column_name
from corehq.apps.userreports.ui.fields import JsonField
from corehq.apps.userreports.util import has_report_builder_access
from dimagi.utils.decorators.memoized import memoized
import six

# This dict maps filter types from the report builder frontend to UCR filter types
REPORT_BUILDER_FILTER_TYPE_MAP = {
    'Choice': 'dynamic_choice_list',
    'Date': 'date',
    'Numeric': 'numeric',
    'Value': 'pre',
}

STATIC_CASE_PROPS = [
    "closed",
    "modified_on",
    "name",
    "opened_on",
    "owner_id",
    "user_id",
]

# PostgreSQL limit = 1600. Sane limit = 500?
MAX_COLUMNS = 500
TEMP_DATA_SOURCE_LIFESPAN = 24 * 60 * 60
SAMPLE_DATA_MAX_ROWS = 100


class FilterField(JsonField):
    """
    A form field with a little bit of validation for report builder report
    filter configuration.
    """

    def validate(self, value):
        super(FilterField, self).validate(value)
        for filter_conf in value:
            if filter_conf.get('format', None) not in (list(REPORT_BUILDER_FILTER_TYPE_MAP) + [""]):
                raise forms.ValidationError("Invalid filter format!")


class Select2(Widget):
    """
    A widget for rendering an input with our knockout "select2" binding.
    Requires knockout to be included on the page.
    """

    def __init__(self, attrs=None, choices=(), ko_value=None):
        self.ko_value = ko_value
        super(Select2, self).__init__(attrs)
        self.choices = list(choices)

    def render(self, name, value, attrs=None, choices=()):
        self.value = '' if value is None else value
        final_attrs = self.build_attrs(attrs, extra_attrs={'name': name})

        return format_html(
            u'<input{final_attrs} type="text" value="{value}" data-bind="select2: {choices}, {ko_binding}">',
            final_attrs=flatatt(final_attrs),
            value=self.value,
            choices=json.dumps(self._choices_for_binding(choices)),
            ko_binding=u"value: {}".format(self.ko_value) if self.ko_value else "",
        )

    def _choices_for_binding(self, choices):
        return [{'id': id, 'text': text} for id, text in chain(self.choices, choices)]


class QuestionSelect(Widget):
    """
    A widget for rendering an input with our knockout "questionsSelect" binding.
    Requires knockout to be included on the page.
    """

    def __init__(self, attrs=None, choices=(), ko_value=None):
        self.ko_value = ko_value
        super(QuestionSelect, self).__init__(attrs)
        self.choices = list(choices)

    def render(self, name, value, attrs=None, choices=()):
        self.value = '' if value is None else value
        final_attrs = self.build_attrs(attrs, extra_attrs={'name': name})

        return format_html(
            u"""
            <input{final_attrs} value="{value}" data-bind='
               questionsSelect: {choices},
               optionsCaption: " ",
               {ko_binding}
            '/>
            """,
            final_attrs=flatatt(final_attrs),
            value=self.value,
            choices=mark_safe(self.render_options(choices)),
            ko_binding='value: {}'.format(self.ko_value),
        )

    def render_options(self, choices):

        def escape(literal):
            return literal.replace('&', '&amp;').replace("'", "&#39;")

        return json.dumps(
            [{'value': escape(v), 'label': escape(l)} for v, l in chain(self.choices, choices)]
        )


class DataSourceProperty(object):
    """
    A container class for information about data source properties

    Class attributes:

    type -- either "case_property", "question", or "meta"
    id -- A string that uniquely identifies this property. For question based
        properties this is the question id, for case based properties this is
        the case property name.
    text -- A human readable representation of the property source. For
        questions this is the question label.
    source -- For questions, this is a dict representing the question as returned
        by Xform.get_questions(), for case properties and form metadata it is just
        the name of the property.
    data_types
    """

    def __init__(self, type, id, text, source, data_types):
        self._type = type
        self._id = id
        self._text = text
        self._source = source
        self._data_types = data_types

    def to_view_model(self):
        """
        Return a dictionary representation to be used by the js
        """
        return {
            "type": self._type,
            "id": self._id,
            "text": self._text,
            "source": self._source,
        }

    def get_text(self):
        return self._text

    def get_type(self):
        return self._type

    def get_id(self):
        return self._id

    def get_source(self):
        return self._source

    def to_report_column_option(self):
        if self._type == PROPERTY_TYPE_QUESTION:
            if self._source['type'] == "MSelect":
                return MultiselectQuestionColumnOption(self._id, self._text, self._source)
            else:
                return QuestionColumnOption(self._id, self._data_types, self._text, self._source)
        elif self._type == PROPERTY_TYPE_META:
            return FormMetaColumnOption(self._id, self._data_types, self._text, self._source)
        else:  # self._type == PROPERTY_TYPE_CASE_PROP
            if self._id == COMPUTED_OWNER_NAME_PROPERTY_ID:
                return OwnernameComputedCasePropertyOption(self._id, self._data_types, self._text)
            elif self._id == COMPUTED_USER_NAME_PROPERTY_ID:
                return UsernameComputedCasePropertyOption(self._id, self._data_types, self._text)
            else:
                return CasePropertyColumnOption(self._id, self._data_types, self._text)

    def _get_filter_format(self, filter_configuration):
        """
        Return the UCR filter type that should be used for the given filter configuration (passed from the UI).
        """
        selected_filter_type = filter_configuration['format']
        if not selected_filter_type or self._type in ('question', 'meta'):
            if self._type == 'question':
                filter_format = get_filter_format_from_question_type(self._source['type'])
            else:
                assert self._type == 'meta'
                filter_format = get_filter_format_from_question_type(self._source[1])
        else:
            filter_format = REPORT_BUILDER_FILTER_TYPE_MAP[selected_filter_type]
        return filter_format

    def _get_agg_type_for_filter_format(self, filter_format):
        """
        ColumnOption.get_indicator(aggregation) uses the aggregation type to determine what data type the indicator
        should be. Therefore, we need to convert filter formats to aggregation types so that we can create the
        correct type of indicator.
        """
        if filter_format == "numeric":
            return AGGREGATION_SUM  # This could also be average, just needs to force numeric
        else:
            return AGGREGATION_SIMPLE

    def to_report_filter(self, configuration, index):
        """
        Return a UCR report filter configuration for the given configuration.
        :param configuration:  dictionary representing options selected in UI.
        :param index: Index of this filter in the list of filters configured by the user.
        :return:
        """
        filter_format = self._get_filter_format(configuration)
        agg = self._get_agg_type_for_filter_format(filter_format)
        column_id = self.to_report_column_option().get_indicator(agg)['column_id']

        filter = {
            "field": column_id,
            "slug": "{}_{}".format(column_id, index),
            "display": configuration["display_text"],
            "type": filter_format
        }
        if configuration['format'] == 'Date':
            filter.update({'compare_as_string': True})
        if filter_format == 'dynamic_choice_list' and self._id == COMPUTED_OWNER_NAME_PROPERTY_ID:
            filter.update({"choice_provider": {"type": "owner"}})
        if filter_format == 'dynamic_choice_list' and self._id == COMPUTED_USER_NAME_PROPERTY_ID:
            filter.update({"choice_provider": {"type": "user"}})
        if configuration.get('pre_value') or configuration.get('pre_operator'):
            filter.update({
                'type': 'pre',  # type could have been "date"
                'pre_operator': configuration.get('pre_operator', None),
                'pre_value': configuration.get('pre_value', []),
            })
        return filter

    def to_report_filter_indicator(self, configuration):
        """
        Return the indicator that would correspond to the given filter configuration
        """
        filter_format = self._get_filter_format(configuration)
        agg = self._get_agg_type_for_filter_format(filter_format)
        return self.to_report_column_option().get_indicator(agg)


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
            prop_map = get_case_properties(
                self.app, [self.source_id], defaults=list(DEFAULT_CASE_PROPERTY_DATATYPES),
                include_parent_properties=False
            )
            self.case_properties = sorted(set(prop_map[self.source_id]) | {'closed'})

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

    def base_item_expression(self, is_multiselect_chart_report, multiselect_field=None):
        """
        Return the base_item_expression for the DataSourceConfiguration.
        Normally this is {}, but if this is a data source for a chart report that is aggregated by a multiselect
        question, then we want one row per multiselect answer.
        :param is_multiselect_chart_report: True if the data source will be used for a chart report aggregated by
            a multiselect question.
        :param multiselect_field: The field that the multiselect aggregated report is aggregated by.
        :return: A base item expression.
        """
        if not is_multiselect_chart_report:
            return {}
        else:
            assert multiselect_field, "multiselect_field is required if is_multiselect_chart_report is True"

            property = self.data_source_properties[multiselect_field]
            path = ['form'] + property.get_source()['value'].split('/')[2:]
            choices = [c['value'] for c in property.get_source()['options']]

            def sub_doc(path):
                if not path:
                    return {"type": "property_name", "property_name": "choice"}
                else:
                    return {
                        "type": "dict",
                        "properties": {
                            path[0]: sub_doc(path[1:])
                        }
                    }

            return {
                "type": "map_items",
                "items_expression": {
                    "type": "iterator",
                    "expressions": [
                        {
                            "type": "dict",
                            "properties": {
                                "choice": c,
                                "doc": {"type": "identity"}
                            }
                        }
                        for c in choices
                    ],
                    "test": {
                        "type": "boolean_expression",
                        "expression": {
                            "type": "property_path",
                            "property_path": ["doc"] + path
                        },
                        "operator": "in_multi",
                        "property_value": {"type": "property_name", "property_name": "choice"}
                    }
                },
                "map_expression": sub_doc(path)
            }

    def indicators(self, columns, filters, is_multiselect_chart_report=False):
        """
        Return a list of indicators to be used in a data source configuration that supports the given columns and
        indicators.
        :param columns: A list of objects representing columns in the report.
            Each object has a "property" and "calculation" key
        :param filters: A list of filter configuration objects
        """

        indicators = OrderedDict()
        for column in columns:
            column_option = self.report_column_options[column['property']]
            for indicator in column_option.get_indicators(column['calculation'], is_multiselect_chart_report):
                indicators.setdefault(str(indicator), indicator)

        for filter_ in filters:
            property_ = self.data_source_properties[filter_['property']]
            indicator = property_.to_report_filter_indicator(filter_)
            indicators.setdefault(str(indicator), indicator)

        return list(indicators.values())

    def all_possible_indicators(self, required_columns, required_filters):
        """
        Will generate a set of possible indicators for the datasource making sure to include the
        provided columns and filters
        """
        indicators = OrderedDict()
        for i in self.indicators(required_columns, required_filters):
            indicators.setdefault(str(i), i)

        for column_option in self.report_column_options.values():
            for agg in column_option.aggregation_options:
                for indicator in column_option.get_indicators(agg):
                    indicators.setdefault(str(indicator), indicator)

        return list(indicators.values())[:MAX_COLUMNS]

    @property
    @memoized
    def data_source_properties(self):
        """
        A dictionary containing the various properties that may be used as indicators
        or columns in the data source or report.

        Keys are strings that uniquely identify properties.
        Values are DataSourceProperty instances.

        >> self.data_source_properties
        {
            "/data/question1": DataSourceProperty(
                type="question",
                id="/data/question1",
                text="Enter the child's name",
                source={
                    'repeat': None,
                    'group': None,
                    'value': '/data/question1',
                    'label': 'question1',
                    'tag': 'input',
                    'type': 'Text'
                },
                data_types=["string"]
            ),
            "meta/deviceID": DataSourceProperty(
                type="meta",
                id="meta/deviceID",
                text="deviceID",
                source=("deviceID", "string"),
                data_types=["string"]
            )
        }
        """

        if self.source_type == 'case':
            return self._get_data_source_properties_from_case(self.case_properties)

        if self.source_type == 'form':
            return self._get_data_source_properties_from_form(self.source_form, self.source_xform)

    @classmethod
    def _get_data_source_properties_from_case(cls, case_properties):
        property_map = {
            'closed': _('Case Closed'),
            'user_id': _('User ID Last Updating Case'),
            'owner_name': _('Case Owner'),
            'mobile worker': _('Mobile Worker Last Updating Case'),
        }

        properties = OrderedDict()
        for property in case_properties:
            if property in DEFAULT_CASE_PROPERTY_DATATYPES:
                data_types = DEFAULT_CASE_PROPERTY_DATATYPES[property]
            else:
                data_types = ["string", "decimal", "datetime"]

            properties[property] = DataSourceProperty(
                type=PROPERTY_TYPE_CASE_PROP,
                id=property,
                text=property_map.get(property, property.replace('_', ' ')),
                source=property,
                data_types=data_types,
            )
        properties[COMPUTED_OWNER_NAME_PROPERTY_ID] = cls._get_owner_name_pseudo_property()
        properties[COMPUTED_USER_NAME_PROPERTY_ID] = cls._get_user_name_pseudo_property()
        return properties

    @staticmethod
    def _get_owner_name_pseudo_property():
        # owner_name is a special pseudo-case property for which
        # the report builder will create a related_doc indicator based
        # on the owner_id of the case.
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_OWNER_NAME_PROPERTY_ID,
            text=_('Case Owner'),
            source=COMPUTED_OWNER_NAME_PROPERTY_ID,
            data_types=["string"],
        )

    @staticmethod
    def _get_user_name_pseudo_property():
        # user_name is a special pseudo case property for which
        # the report builder will create a related_doc indicator based on the
        # user_id of the case
        return DataSourceProperty(
            type=PROPERTY_TYPE_CASE_PROP,
            id=COMPUTED_USER_NAME_PROPERTY_ID,
            text=_('Mobile Worker Last Updating Case'),
            source=COMPUTED_USER_NAME_PROPERTY_ID,
            data_types=["string"],
        )

    @staticmethod
    def _get_data_source_properties_from_form(form, form_xml):
        property_map = {
            'username': _('User Name'),
            'userID': _('User ID'),
            'timeStart': _('Date Form Started'),
            'timeEnd': _('Date Form Completed'),
        }
        properties = OrderedDict()
        questions = form_xml.get_questions([])
        for prop in FORM_METADATA_PROPERTIES:
            question_type = prop[1]
            data_type = {
                "DateTime": "datetime",
                "Text": "string",
            }[question_type]
            properties[prop[0]] = DataSourceProperty(
                type=PROPERTY_TYPE_META,
                id=prop[0],
                text=property_map.get(prop[0], prop[0]),
                source=prop,
                data_types=[data_type]
            )
        for question in questions:
            if question['type'] == "DataBindOnly":
                data_types = ["string", "decimal", "datetime"]
            elif question['type'] in ("Int", "Double", "Long"):
                data_types = ["decimal"]
            else:
                data_types = ["string"]
            properties[question['value']] = DataSourceProperty(
                type=PROPERTY_TYPE_QUESTION,
                id=question['value'],
                text=question['label'],
                source=question,
                data_types=data_types,
            )
        if form.get_app().auto_gps_capture:
            properties['location'] = DataSourceProperty(
                type=PROPERTY_TYPE_META,
                id='location',
                text='location',
                source=(['location', '#text'], 'Text'),
                data_types=["string"],
            )
        return properties

    @property
    @memoized
    def report_column_options(self):
        options = OrderedDict()
        for id_, prop in six.iteritems(self.data_source_properties):
            options[id_] = prop.to_report_column_option()

        # NOTE: Count columns aren't useful for table reports. But we need it in the column options because
        # the options are currently static, after loading the report builder a user can switch to an aggregated
        # report.
        count_col = CountColumn("Number of Cases" if self.source_type == "case" else "Number of Forms")
        options[count_col.get_property()] = count_col

        return options

    @property
    @memoized
    def data_source_name(self):
        if self.source_type == 'form':
            return u"{} (v{})".format(self.source_form.default_name(), self.app.version)
        if self.source_type == 'case':
            return u"{} (v{})".format(self.source_id, self.app.version)

    def _ds_config_kwargs(self, indicators, is_multiselect_chart_report=False, multiselect_field=None):
        if is_multiselect_chart_report:
            base_item_expression = self.base_item_expression(True, multiselect_field)
        else:
            base_item_expression = self.base_item_expression(False)

        return dict(
            display_name=self.data_source_name,
            referenced_doc_type=self.source_doc_type,
            configured_filter=self.filter,
            configured_indicators=indicators,
            base_item_expression=base_item_expression,
            meta=DataSourceMeta(build=DataSourceBuildInformation(
                source_id=self.source_id,
                app_id=self.app._id,
                app_version=self.app.version,
            ))
        )

    def get_temp_ds_config_kwargs(self, required_columns, required_filters):
        indicators = self.all_possible_indicators(required_columns, required_filters)
        return self._ds_config_kwargs(indicators)

    def get_ds_config_kwargs(self, columns, filters,
                             is_multiselect_chart_report=False, multiselect_field=None):
        indicators = self.indicators(
            columns,
            filters,
            is_multiselect_chart_report
        )
        return self._ds_config_kwargs(indicators, is_multiselect_chart_report, multiselect_field)


class DataSourceForm(forms.Form):
    report_name = forms.CharField()

    def __init__(self, domain, max_allowed_reports, *args, **kwargs):
        super(DataSourceForm, self).__init__(*args, **kwargs)
        self.domain = domain
        self.max_allowed_reports = max_allowed_reports

        # TODO: Map reports.
        self.app_source_helper = ApplicationDataSourceUIHelper()
        self.app_source_helper.source_type_field.label = _('Forms or Cases')
        self.app_source_helper.source_type_field.choices = [("case", _("Cases")), ("form", _("Forms"))]
        self.app_source_helper.source_field.label = '<span data-bind="text: labelMap[sourceType()]"></span>'
        self.app_source_helper.bootstrap(self.domain)
        report_source_fields = self.app_source_helper.get_fields()
        report_source_help_texts = {
            "source_type": _(
                "<strong>Form</strong>: Display data from form submissions.<br/>"
                "<strong>Case</strong>: Display data from your cases. You must be using case management for this "
                "option."),
            "application": _("Which application should the data come from?"),
            "source": _("Choose the case type or form from which to retrieve data for this report."),
        }
        self.fields.update(report_source_fields)

        self.helper = FormHelper()
        self.helper.form_class = "form form-horizontal"
        self.helper.form_id = "report-builder-form"
        self.helper.label_class = 'col-sm-3 col-md-2 col-lg-2'
        self.helper.field_class = 'col-sm-9 col-md-8 col-lg-6'

        report_source_crispy_fields = []
        for k in report_source_fields.keys():
            if k in report_source_help_texts:
                report_source_crispy_fields.append(hqcrispy.FieldWithHelpBubble(
                    k, help_bubble_text=report_source_help_texts[k]
                ))
            else:
                report_source_crispy_fields.append(k)

        self.helper.layout = crispy.Layout(
            crispy.Fieldset(
                _('Report'),
                hqcrispy.FieldWithHelpBubble(
                    'report_name',
                    help_bubble_text=_(
                        'Web users will see this name in the "Reports" section of CommCareHQ and can click to '
                        'view the report'
                    )
                )
            ),
            crispy.Fieldset(
                _('Data'), *report_source_crispy_fields
            ),
            hqcrispy.FormActions(
                StrictButton(
                    _('Next'),
                    type="submit",
                    css_id='js-next-data-source',
                    css_class="btn-primary",
                )
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

        existing_reports = ReportConfiguration.by_domain(self.domain)
        builder_reports = [report for report in existing_reports if report.report_meta.created_by_builder]
        if has_report_builder_access(self.domain) and len(builder_reports) >= self.max_allowed_reports:
            # Don't show the warning when domain does not have report buidler access, because this is just a
            # preview and the report will not be saved.
            raise forms.ValidationError(_(
                "Too many reports!\n"
                "Creating this report would cause you to go over the maximum "
                "number of report builder reports allowed in this domain. Your "
                "limit is {number}. "
                "To continue, delete another report and try again. "
            ).format(number=self.max_allowed_reports))

        return cleaned_data


_shared_properties = ['exists_in_current_version', 'display_text', 'property', 'data_source_field']
UserFilterViewModel = namedtuple("UserFilterViewModel", _shared_properties + ['format'])
DefaultFilterViewModel = namedtuple("DefaultFilterViewModel",
                                    _shared_properties + ['format', 'pre_value', 'pre_operator'])
ColumnViewModel = namedtuple("ColumnViewModel", _shared_properties + ['calculation'])


class ConfigureNewReportBase(forms.Form):
    user_filters = FilterField(required=False)
    default_filters = FilterField(required=False)
    report_title = forms.CharField(widget=forms.HiddenInput, required=False)
    report_description = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        """
        This form can be used to create a new ReportConfiguration, or to modify
        an existing one if existing_report is set.
        """
        super(ConfigureNewReportBase, self).__init__(*args, **kwargs)
        self.existing_report = existing_report

        if self.existing_report:
            self._bootstrap(self.existing_report)
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
        self.report_column_options = self.ds_builder.report_column_options

        self.data_source_properties = self.ds_builder.data_source_properties

        self._report_columns_by_column_id = {}
        for column in self.report_column_options.values():
            for agg in column.aggregation_options:
                indicators = column.get_indicators(agg)
                for i in indicators:
                    self._report_columns_by_column_id[i['column_id']] = column

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
        app_id = existing_report.config.meta.build.app_id
        if app_id:
            self.app = Application.get(app_id)
        else:
            raise BadBuilderConfigError(_(
                "Report builder data source doesn't reference an application. "
                "It is likely this report has been customized and it is no longer editable. "
            ))

    @property
    def _configured_columns(self):
        """
        To be used by DataSourceBuilder.indicators()
        """
        configured_columns = self.cleaned_data['columns']
        location = self.cleaned_data.get("location")
        if location:
            configured_columns += [{
                "property": location,
                "calculation": AGGREGATION_SIMPLE  # Not aggregated
            }]
        return configured_columns

    def _get_data_source_configuration_kwargs(self):
        filters = self.cleaned_data['user_filters'] + self.cleaned_data['default_filters']
        ms_field = self._report_aggregation_cols[0] if self._is_multiselect_chart_report else None
        return self.ds_builder.get_ds_config_kwargs(self._configured_columns,
                                                    filters,
                                                    self._is_multiselect_chart_report,
                                                    ms_field)

    def _build_data_source(self):
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            # The uuid gets truncated, so it's not really universally unique.
            table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
            **self._get_data_source_configuration_kwargs()
        )
        data_source_config.validate()
        data_source_config.save()
        tasks.rebuild_indicators.delay(data_source_config._id)
        return data_source_config._id

    def update_report(self):

        data_source = DataSourceConfiguration.get(self.existing_report.config_id)
        if data_source.get_report_count() > 1:
            # If another report is pointing at this data source, create a new
            # data source for this report so that we can change the indicators
            # without worrying about breaking another report.
            data_source_config_id = self._build_data_source()
            self.existing_report.config_id = data_source_config_id
        else:
            indicators = self.ds_builder.indicators(
                self._configured_columns,
                self.cleaned_data['user_filters'] + self.cleaned_data['default_filters'],
                self._is_multiselect_chart_report,
            )
            if data_source.configured_indicators != indicators:
                for property_name, value in six.iteritems(self._get_data_source_configuration_kwargs()):
                    setattr(data_source, property_name, value)
                data_source.save()
                tasks.rebuild_indicators.delay(data_source._id)

        self.existing_report.aggregation_columns = self._report_aggregation_cols
        self.existing_report.columns = self._report_columns
        self.existing_report.filters = self._report_filters
        self.existing_report.configured_charts = self._report_charts
        self.existing_report.title = self.cleaned_data['report_title'] or _("Report Builder Report")
        self.existing_report.description = self.cleaned_data['report_description']
        self.existing_report.validate()
        self.existing_report.save()
        return self.existing_report

    def create_report(self):
        """
        Creates data source and report config.

        :raises BadSpecError if validation fails when building data source, or report is invalid
        """
        data_source_config_id = self._build_data_source()
        report = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_config_id,
            title=self.cleaned_data['report_title'] or self.report_name,
            aggregation_columns=self._report_aggregation_cols,
            columns=self._report_columns,
            filters=self._report_filters,
            configured_charts=self._report_charts,
            description=self.cleaned_data['report_description'],
            report_meta=ReportMeta(
                created_by_builder=True,
                report_builder_version="2.0",
                builder_report_type=self.report_type
            )
        )
        report.validate()
        report.save()
        return report

    def create_temp_report(self, data_source_id, username):
        """
        Updates the datasource then creates and saves a report config.

        :raises BadSpecError if report is invalid
        """

        self._update_temp_datasource(data_source_id, username)
        report = ReportConfiguration(
            domain=self.domain,
            config_id=data_source_id,
            title=self.report_name,
            aggregation_columns=self._report_aggregation_cols,
            columns=self._report_columns,
            filters=self._report_filters,
            configured_charts=self._report_charts,
            report_meta=ReportMeta(
                created_by_builder=True,
                report_builder_version="2.0",
                builder_report_type=self.report_type
            )
        )
        report.validate()
        report.save()
        return report

    def create_temp_data_source(self, username):
        """
        Build a temp datasource and return the ID
        """

        filters = [f._asdict() for f in self.initial_user_filters + self.initial_default_filters]
        columns = [c._asdict() for c in self.initial_columns]

        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            table_id=_clean_table_name(self.domain, uuid.uuid4().hex),
            **self.ds_builder.get_temp_ds_config_kwargs(columns, filters)
        )
        data_source_config.validate()
        data_source_config.save()

        # expire the data source
        always_eager = hasattr(settings, "CELERY_ALWAYS_EAGER") and settings.CELERY_ALWAYS_EAGER
        # CELERY_ALWAYS_EAGER will cause the data source to be deleted immediately. Switch it off temporarily
        settings.CELERY_ALWAYS_EAGER = False
        tasks.delete_data_source_task.apply_async(
            (self.domain, data_source_config._id),
            countdown=TEMP_DATA_SOURCE_LIFESPAN
        )
        settings.CELERY_ALWAYS_EAGER = always_eager

        tasks.rebuild_indicators(data_source_config._id,
                                 username,
                                 limit=SAMPLE_DATA_MAX_ROWS)  # Do synchronously
        self._filter_data_source_changes(data_source_config._id)
        return data_source_config._id

    @staticmethod
    def _filter_data_source_changes(data_source_config_id):
        """
        Add filter to data source to prevent it from being updated by DB changes
        """
        # Reload using the ID instead of just passing in the object to avoid ResourceConflicts
        data_source_config = DataSourceConfiguration.get(data_source_config_id)
        data_source_config.configured_filter = {
            # An expression that is always false:
            "type": "boolean_expression",
            "operator": "eq",
            "expression": 1,
            "property_value": 2,
        }
        data_source_config.validate()
        data_source_config.save()

    def _update_temp_datasource(self, data_source_config_id, username):
        data_source_config = DataSourceConfiguration.get(data_source_config_id)

        filters = self.cleaned_data['user_filters'] + self.cleaned_data['default_filters']
        required_column_set = set([c["column_id"]
                                   for c in self.ds_builder.indicators(self._configured_columns, filters)])
        current_column_set = set([c["column_id"] for c in data_source_config.configured_indicators])
        missing_columns = [c for c in required_column_set if c not in current_column_set]

        # rebuild the table
        if missing_columns:
            temp_config = self.ds_builder.get_temp_ds_config_kwargs(self._configured_columns, filters)
            data_source_config.configured_indicators = temp_config["configured_indicators"]
            data_source_config.configured_filter = temp_config["configured_filter"]
            data_source_config.base_item_expression = temp_config["base_item_expression"]
            data_source_config.validate()
            data_source_config.save()
            tasks.rebuild_indicators(data_source_config._id,
                                     username,
                                     limit=SAMPLE_DATA_MAX_ROWS)  # Do synchronously
            self._filter_data_source_changes(data_source_config._id)

    @property
    @memoized
    def initial_default_filters(self):
        return [self._get_view_model(f) for f in self.existing_report.prefilters] if self.existing_report else []

    @property
    @memoized
    def initial_user_filters(self):
        if self.existing_report:
            return [self._get_view_model(f) for f in self.existing_report.filters_without_prefilters]
        if self.source_type == 'case':
            return self._default_case_report_filters
        else:
            # self.source_type == 'form'
            return self._default_form_report_filters

    @property
    @memoized
    def _default_case_report_filters(self):
        return [
            UserFilterViewModel(
                exists_in_current_version=True,
                property='closed',
                data_source_field=None,
                display_text=_('Closed'),
                format='Choice',
            ),
            UserFilterViewModel(
                exists_in_current_version=True,
                property=COMPUTED_OWNER_NAME_PROPERTY_ID,
                data_source_field=None,
                display_text=_('Case Owner'),
                format='Choice',
            ),
        ]

    @property
    @memoized
    def _default_form_report_filters(self):
        return [
            UserFilterViewModel(
                exists_in_current_version=True,
                property='timeEnd',
                data_source_field=None,
                display_text='Form completion time',
                format='Date',
            ),
        ]

    def _get_view_model(self, filter):
        """
        Given a ReportFilter, return a FilterViewModel representing
        the knockout view model representing this filter in the report builder.

        """
        exists = self._column_exists(filter['field'])
        if filter['type'] == 'pre':
            return DefaultFilterViewModel(
                exists_in_current_version=exists,
                display_text='',
                format='Value' if filter['pre_value'] else 'Date',
                property=self._get_property_id_by_indicator_id(filter['field']) if exists else None,
                data_source_field=filter['field'] if not exists else None,
                pre_value=filter['pre_value'],
                pre_operator=filter['pre_operator'],
            )
        else:
            filter_type_map = {
                'dynamic_choice_list': 'Choice',
                # This exists to handle the `closed` filter that might exist
                'choice_list': 'Choice',
                'date': 'Date',
                'numeric': 'Numeric'
            }
            return UserFilterViewModel(
                exists_in_current_version=exists,
                display_text=filter['display'],
                format=filter_type_map[filter['type']],
                property=self._get_property_id_by_indicator_id(filter['field']) if exists else None,
                data_source_field=filter['field'] if not exists else None
            )

    def _get_column_option_by_indicator_id(self, indicator_column_id):
        """
        Return the ColumnOption corresponding to the given indicator id.
        NOTE: This currently assumes that there is a one-to-one mapping between
        ColumnOptions and data source indicators, but we may want to remove
        this assumption as we add functionality to the report builder.
        :param indicator_column_id: The column_id field of a data source
            indicator configuration.
        :return: The corresponding ColumnOption
        """
        return self._report_columns_by_column_id[indicator_column_id]

    def _get_property_id_by_indicator_id(self, indicator_column_id):
        """
        Return the data source property id corresponding to the given data
        source indicator column id.
        :param indicator_column_id: The column_id field of a data source indicator
            configuration dictionary
        :return: A DataSourceProperty property id, e.g. "/data/question1"
        """
        column = self._report_columns_by_column_id.get(indicator_column_id)
        if column:
            return column.get_property()

    def _column_exists(self, column_id):
        """
        Return True if this column corresponds to a question/case property in
        the current version of this form/case configuration.

        This could be true if a user makes a report, modifies the app, then
        edits the report.

        column_id is a string like "data_date_q_d1b3693e"
        """
        return column_id in self._report_columns_by_column_id

    def _convert_v1_column_id_to_current_format(self, column_id):
        """
        Assuming column_id does not exist, assume it's from version 1 of the report builder, and attempt to convert
        it to the current version.

        This is needed because previously hidden value questions and case property columns didn't have a datatype
        in their ids, but the builder now expects that, so this attempts to just append a datatype.
        """
        return column_id + "_string"


    def _get_multiselect_indicator_id(self, column_field, indicators):
        """
        If this column_field corresponds to a multiselect data source indicator, then return the id of the
        indicator. Otherwise return None.
        :param column_field: The "field" property of a report column
        :return: a data source indicator id
        """
        indicator_id = "_".join(column_field.split("_")[:-1])
        for indicator in indicators:
            if indicator['column_id'] == indicator_id and indicator['type'] == 'choice_list':
                return indicator_id
        return None

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']

    @property
    def _report_columns(self):
        return []

    @property
    def _is_multiselect_chart_report(self):
        return False

    @property
    def _report_filters(self):
        """
        Return the dict filter configurations to be used by the
        ReportConfiguration that this form produces.
        """
        def _make_report_filter(conf, index):
            property = self.data_source_properties[conf["property"]]
            return property.to_report_filter(conf, index)

        user_filter_configs = self.cleaned_data['user_filters']
        default_filter_configs = self.cleaned_data['default_filters']
        filters = [_make_report_filter(f, i) for i, f in enumerate(user_filter_configs + default_filter_configs)]
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


class ConfigureListReportForm(ConfigureNewReportBase):
    report_type = 'list'
    columns = JsonField(
        expected_type=list,
        null_values=([],),
        required=False,
        widget=forms.HiddenInput,
    )

    @property
    @memoized
    def initial_columns(self):
        if self.existing_report:
            reverse_agg_map = {
                UCR_REPORT_AGGREGATION_SIMPLE: AGGREGATION_GROUP_BY,
                UCR_REPORT_AGGREGATION_AVG: AGGREGATION_AVERAGE,
                UCR_REPORT_AGGREGATION_SUM: AGGREGATION_SUM,
                UCR_REPORT_AGGREGATION_EXPAND: AGGREGATION_COUNT_PER_CHOICE,
            }
            added_multiselect_columns = set()
            cols = []
            for c in self.existing_report.columns:
                mselect_indicator_id = self._get_multiselect_indicator_id(
                    c['field'], self.existing_report.config.configured_indicators
                )
                indicator_id = mselect_indicator_id or c['field']
                display = c['display']
                agg = c.get("aggregation")
                exists = self._column_exists(indicator_id)
                if not exists:
                    possibly_corrected_column_id = self._convert_v1_column_id_to_current_format(indicator_id)
                    if self._column_exists(possibly_corrected_column_id):
                        exists = True
                        indicator_id = possibly_corrected_column_id

                if mselect_indicator_id:
                    if mselect_indicator_id not in added_multiselect_columns:
                        added_multiselect_columns.add(mselect_indicator_id)
                        display = MultiselectQuestionColumnOption.LABEL_DIVIDER.join(
                            display.split(MultiselectQuestionColumnOption.LABEL_DIVIDER)[:-1]
                        )
                        agg = AGGREGATION_COUNT_PER_CHOICE
                    else:
                        continue

                cols.append(
                    ColumnViewModel(
                        display_text=display,
                        exists_in_current_version=exists,
                        property=(
                            self._get_column_option_by_indicator_id(indicator_id).get_property()
                            if exists else None
                        ),
                        data_source_field=indicator_id if not exists else None,
                        calculation=reverse_agg_map.get(agg, AGGREGATION_COUNT_PER_CHOICE)
                    )
                )
            return cols
        else:
            return self._get_default_columns()

    def _get_default_columns(self):
        if self.source_type == "case":
            return self._get_default_case_report_columns()
        else:
            return self._get_default_form_report_columns()

    def _get_default_case_report_columns(self):
        cols = []
        cols.append(ColumnViewModel(
            display_text="Name",
            exists_in_current_version=True,
            property="name",
            data_source_field=(
                self.data_source_properties['name']
                    .to_report_column_option()
                    .get_indicator(AGGREGATION_COUNT_PER_CHOICE)['column_id']),
            calculation=AGGREGATION_COUNT_PER_CHOICE
        ))
        cols.append(ColumnViewModel(
            display_text="Owner",
            exists_in_current_version=True,
            property=COMPUTED_OWNER_NAME_PROPERTY_ID,
            data_source_field=(
                self.data_source_properties[COMPUTED_OWNER_NAME_PROPERTY_ID]
                    .to_report_column_option()
                    .get_indicator(AGGREGATION_COUNT_PER_CHOICE)['column_id']),
            calculation=AGGREGATION_COUNT_PER_CHOICE
        ))
        case_props_found = 0

        skip_list = set([COMPUTED_OWNER_NAME_PROPERTY_ID, COMPUTED_USER_NAME_PROPERTY_ID] + STATIC_CASE_PROPS)
        for prop in self.data_source_properties.values():
            if prop.get_type() == PROPERTY_TYPE_CASE_PROP and prop.get_id() not in skip_list:
                case_props_found += 1
                cols.append(ColumnViewModel(
                    display_text=prop.get_text(),
                    exists_in_current_version=True,
                    property=prop.get_id(),
                    data_source_field=prop.to_report_column_option().get_indicator(AGGREGATION_COUNT_PER_CHOICE)['column_id'],
                    calculation=AGGREGATION_COUNT_PER_CHOICE,
                ))
                if case_props_found == 3:
                    break
        return cols

    def _get_default_form_report_columns(self):
        cols = []
        prop = self.data_source_properties['username']
        cols.append(ColumnViewModel(
            display_text=prop.get_text(),
            exists_in_current_version=True,
            property=prop.get_id(),
            data_source_field=prop.to_report_column_option().get_indicator(AGGREGATION_COUNT_PER_CHOICE)['column_id'],
            calculation=AGGREGATION_COUNT_PER_CHOICE
        ))
        questions = [p for p in self.data_source_properties.values()
                     if p.get_type() == PROPERTY_TYPE_QUESTION]
        if len(questions) > 9:
            questions = questions[:9]
        for q in questions:
            cols.append(ColumnViewModel(
                display_text=q.get_text(),
                exists_in_current_version=True,
                property=q.get_id(),
                data_source_field=q.get_id(),
                calculation=AGGREGATION_COUNT_PER_CHOICE,
            ))
        return cols


    @property
    def _report_columns(self):
        # TODO SS - this seems wrong (we should be using the column option to do this)
        columns = []
        for i, conf in enumerate(self.cleaned_data['columns']):
            columns.extend(
                self.ds_builder.report_column_options[conf['property']].to_column_dicts(
                    i, conf.get('display_text', conf['property']), UCR_REPORT_AGGREGATION_SIMPLE
                )
            )
        return columns

    @property
    def _report_aggregation_cols(self):
        return ['doc_id']


class ConfigureTableReportForm(ConfigureListReportForm):
    report_type = 'table'
    chart = forms.CharField(widget=forms.HiddenInput)

    @property
    def _report_charts(self):

        def get_non_agged_columns():
            return [c for c in self._report_columns if c['aggregation'] != UCR_REPORT_AGGREGATION_SIMPLE]

        def get_agged_columns():
            return [c for c in self._report_columns if c['aggregation'] == UCR_REPORT_AGGREGATION_SIMPLE]

        if get_non_agged_columns():
            if self.cleaned_data['chart'] == "bar":
                return [{
                    "type": "multibar",
                    "x_axis_column": get_agged_columns()[0]['column_id'] if get_agged_columns() else '',
                    # TODO: Possibly use more columns?
                    "y_axis_columns": [
                        {"column_id": c["column_id"], "display": c["display"]} for c in get_non_agged_columns()
                    ],
                }]
            elif self.cleaned_data['chart'] == "pie":
                return [{
                    "type": "pie",
                    "aggregation_column": get_agged_columns()[0]['column_id'],
                    "value_column": get_non_agged_columns()[0]['column_id'],
                }]
        return []

    @property
    def _is_multiselect_chart_report(self):
        """
        Return True if this is a chart report aggregated by a multiselect question.
        The data sources for these sorts of reports are handled differently than other reports.
        """
        # Disabling this feature for now
        return False
        # if self.cleaned_data['chart'] in ("pie", "bar"):
        #     agg_property = self.data_source_properties[self.cleaned_data['group_by'][0]]
        #     return agg_property.type == "question" and agg_property.source['type'] == "MSelect"
        # return False

    @property
    def _report_columns(self):
        columns = []
        for i, conf in enumerate(self.cleaned_data['columns']):
            column = self.ds_builder.report_column_options[conf['property']]
            columns.extend(
                column.to_column_dicts(
                    index=i,
                    display_text=conf['display_text'],
                    aggregation=conf['calculation'],
                    is_aggregated_on=conf.get('calculation') == AGGREGATION_GROUP_BY
                ))
        return columns

    @property
    @memoized
    def _report_aggregation_cols(self):
        return [
            self.ds_builder.report_column_options[conf['property']].get_indicator(AGGREGATION_GROUP_BY)['column_id']
            for conf in self.cleaned_data['columns'] if conf['calculation'] == AGGREGATION_GROUP_BY
        ]


class ConfigureMapReportForm(ConfigureListReportForm):
    report_type = 'map'
    location = forms.ChoiceField(label="Location field", required=False)

    def __init__(self, report_name, app_id, source_type, report_source_id, existing_report=None, *args, **kwargs):
        super(ConfigureMapReportForm, self).__init__(
            report_name, app_id, source_type, report_source_id, existing_report, *args, **kwargs
        )
        self.fields['location'].choices = self._location_choices

        # Set initial value of location
        if self.existing_report and existing_report.location_column_id:
            existing_loc_col = existing_report.location_column_id
            self.fields['location'].initial = self._get_property_id_by_indicator_id(existing_loc_col)

    @property
    def _location_choices(self):
        return [(p.get_id(), p.get_text()) for p in self.data_source_properties.values()]

    @property
    @memoized
    def initial_columns(self):
        columns = super(ConfigureMapReportForm, self).initial_columns

        # Remove the location indicator from the columns.
        # It gets removed because we want it to be a column in the report,
        # but we don't want it to appear in the builder.
        if self.existing_report and self.existing_report.location_column_id:
            col_id = self.existing_report.location_column_id
            location_property = self._get_property_id_by_indicator_id(col_id)
            return [c for c in columns if c.property != location_property]
        return columns

    @property
    def location_field(self):
        return self.cleaned_data["location"]

    @property
    def _report_columns(self):
        columns = super(ConfigureMapReportForm, self)._report_columns

        if self.location_field:
            loc_column = self.data_source_properties[self.location_field].to_report_column_option()
            loc_indicator = loc_column.get_indicator(AGGREGATION_SIMPLE)
            loc_field_id = loc_indicator['column_id']
            loc_field_text = loc_column.get_default_display()

            displaying_loc_column = False
            for c in columns:
                if c['field'] == loc_field_id:
                    c['type'] = "location"
                    displaying_loc_column = True
                    break

            # Add the location indicator to the columns if it's not already present.
            if not displaying_loc_column:
                columns = columns + [{
                    "column_id": loc_field_id,
                    "type": "location",
                    'field': loc_field_id,
                    'display': loc_field_text
                }]

        return columns
