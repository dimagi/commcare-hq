from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.userreports.datatypes import NUMERIC_TYPE_CHOICES
from corehq.apps.userreports.reports.builder import (
    make_case_property_indicator,
    make_multiselect_question_indicator,
)
from corehq.apps.userreports.app_manager.data_source_meta import make_form_question_indicator, \
    make_form_meta_block_indicator
from corehq.apps.userreports.reports.builder.const import (
    UCR_AGG_AVG,
    UCR_AGG_EXPAND,
    UCR_AGG_SIMPLE,
    UCR_AGG_SUM,
    UI_AGG_AVERAGE,
    UI_AGG_COUNT_PER_CHOICE,
    UI_AGG_GROUP_BY,
    UI_AGG_SUM,
    UI_AGGREGATIONS,
)
from corehq.apps.userreports.sql import get_column_name
from corehq.util.python_compatibility import soft_assert_type_text
from memoized import memoized
import six


class ColumnOption(object):
    """
    This class represents column options in the report builder. That is, a case property, meta property, or form
    question that can be selected to be shown in the report.
    """

    def __init__(self, property, data_types, default_display):
        self._property = property  # A string uniquely identifying the property
        self._data_types = data_types

        self._default_display = default_display

    def get_default_display(self):
        return self._default_display

    def get_property(self):
        return self._property

    def to_view_model(self):
        """
        This dictionary will used by the js on the page
        """
        return {
            "id": self._property,
            "display": self._default_display,
            "aggregation_options": self.aggregation_options
        }

    @property
    @memoized
    def aggregation_options(self):
        if self._has_a_numeric_type():
            return UI_AGGREGATIONS  # All aggregations can be applied to numbers
        else:
            return (UI_AGG_GROUP_BY, UI_AGG_COUNT_PER_CHOICE)

    def _get_ucr_aggregation(self, ui_aggregation):
        """
        Convert an aggregation value selected in the UI to an aggregation value to be used in the UCR
        configuration.

        :param ui_aggregation: UI aggregation value
        :return: UCR config aggregation value
        """
        assert ui_aggregation in UI_AGGREGATIONS, (
            '"{}" is not recognised as a Report Builder UI aggregation'.format(ui_aggregation)
        )
        aggregation_map = {
            UI_AGG_AVERAGE: UCR_AGG_AVG,
            UI_AGG_COUNT_PER_CHOICE: UCR_AGG_EXPAND,
            UI_AGG_GROUP_BY: UCR_AGG_SIMPLE,
            UI_AGG_SUM: UCR_AGG_SUM,
            None: UCR_AGG_SIMPLE,
        }
        return aggregation_map[ui_aggregation]

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        """
        Get the indicator corresponding to this column option. This function will raise an exception if more than
        one indicator corresponds to this column.
        """
        raise NotImplementedError

    def get_indicators(self, ui_aggregation, is_multiselect_chart_report=False):
        """
        Return the indicators corresponding to this column option.
        """
        return [self._get_indicator(ui_aggregation)]

    def to_column_dicts(self, index, display_text, ui_aggregation, is_aggregated_on=False):
        """
        Return a UCR report column configuration dictionary

        :param index: The index of the column in the list of columns, e.g. 0, 1, 2, etc.
        :param display_text: The label for this column
        :param ui_aggregation: What sort of aggregation the user selected for this column in the UI
        :param is_aggregated_on: True if the user chose to "group by" this column
        """
        # Use get_indicators() instead of _get_indicator() to find column_id because otherwise this will break
        # for MultiselectQuestionColumnOption instances when ui_aggregation != "Group By"
        column_id = self.get_indicators(ui_aggregation)[0]['column_id']
        return [{
            "format": "default",
            "aggregation": self._get_ucr_aggregation(ui_aggregation),  # NOTE: "aggregation" is a UCR aggregation
            "field": column_id,
            "column_id": "column_{}".format(index),
            "type": "field",
            "display": display_text,
            "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'},
        }]

    def _has_a_numeric_type(self):
        return any([datatype in self._data_types for datatype in NUMERIC_TYPE_CHOICES])


class QuestionColumnOption(ColumnOption):
    """
    A form question that can be displayed in a report builder report.
    """

    def __init__(self, property, data_types, default_display, question_source):
        super(QuestionColumnOption, self).__init__(property, data_types, default_display)
        self._question_source = question_source

    def to_view_model(self):
        ret = super(QuestionColumnOption, self).to_view_model()
        ret['question_source'] = self._question_source
        return ret

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        """
        Return the report config snippet for the data source indicator for this form question column option
        """
        assert ui_aggregation in UI_AGGREGATIONS, (
            '"{}" is not an aggregation recognised by the Report Builder interface.'.format(ui_aggregation)
        )
        if ui_aggregation in (UI_AGG_SUM, UI_AGG_AVERAGE):
            data_type = "decimal"
        else:
            data_type = None  # use the default

        column_id = get_column_name(self._property.strip("/"), suffix=data_type)
        return make_form_question_indicator(
            self._question_source, column_id, data_type, root_doc=is_multiselect_chart_report
        )


class FormMetaColumnOption(ColumnOption):
    """
    A form meta property (like received_on, time_start, user_id, etc.) that can be displayed in a report builder
    report.
    """

    def __init__(self, property, data_types, default_display, meta_property_spec):
        super(FormMetaColumnOption, self).__init__(property, data_types, default_display)
        self._meta_property_spec = meta_property_spec

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        # ui_aggregation parameter is never used because we need not infer the data type
        # self._question_source is a tuple of (identifier, datatype)
        identifier = self._meta_property_spec[0]
        if isinstance(identifier, six.string_types):
            soft_assert_type_text(identifier)
            identifier = [identifier]
        identifier = "/".join(identifier)
        column_id = get_column_name(identifier.strip("/"))
        return make_form_meta_block_indicator(
            self._meta_property_spec, column_id, root_doc=is_multiselect_chart_report
        )


class MultiselectQuestionColumnOption(QuestionColumnOption):
    """
    A multiselect form question that can be displayed in a report builder report.
    We use special logic for multiselect questions.
    """
    LABEL_DIVIDER = " - "

    def __init__(self, property, default_display, question_source):
        super(MultiselectQuestionColumnOption, self).__init__(
            property, ["string"], default_display, question_source
        )

    def to_column_dicts(self, index, display_text, ui_aggregation, is_aggregated_on=False):
        assert ui_aggregation in (UI_AGG_COUNT_PER_CHOICE, UI_AGG_GROUP_BY)

        if is_aggregated_on:
            return [{
                "format": "default",
                "aggregation": self._get_ucr_aggregation(ui_aggregation),
                "field": self._get_filter_and_agg_indicator()['column_id'],
                "column_id": "column_{}".format(index),
                "type": "field",
                "display": display_text,
                "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'},
            }]

        columns = []
        for choice_index, choice in enumerate(self._question_source['options']):
            columns.append({
                "type": "field",
                "column_id": "column_{}_{}".format(index, choice_index),
                "format": "default",
                "aggregation": UCR_AGG_SUM,
                "field": "{}_{}".format(self._get_choice_indicator()['column_id'], choice['value']),
                "display": display_text + self.LABEL_DIVIDER + choice['label']
            })

        return columns

    def _get_filter_and_agg_indicator(self):
        """
        Return the data source indicator that will be used for filtering, or aggregating on this question (but not
        display)
        """
        column_id = get_column_name(self._property.strip("/"))
        return make_form_question_indicator(self._question_source, column_id)

    def _get_choice_indicator(self):
        """
        Return the data source indicator that will be used for displaying this question in the report (but not
        filtering or aggregation)
        """
        # column_id must match that used in _get_filter_and_agg_indicator() because the data will come from the
        # same data source column
        column_id = get_column_name(self._property.strip("/"))
        return make_multiselect_question_indicator(self._question_source, column_id)

    def get_indicators(self, ui_aggregation, is_multiselect_chart_report=False):
        """
        Return the report config snippets that specify the data source indicator that will be used for
        aggregating this question, and the data source indicator for the multi-select question's choices.
        """
        return [self._get_filter_and_agg_indicator(), self._get_choice_indicator()]

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        """
        Validate that this is being called with ui_aggregation == "Group By" (i.e. not actually aggregating).

        (Aggregations of MultiselectQuestionColumnOption can aggregate either of two indicators; its value or its
        choices, so self.get_indicators() must be used instead.)
        """
        assert ui_aggregation == UI_AGG_GROUP_BY, (
            'Column options for multi-select questions have multiple indicators for all aggregations except '
            '"group by". For "{}" aggregation you need to use get_indicators() instead.'.format(ui_aggregation)
        )
        return super(MultiselectQuestionColumnOption, self)._get_indicator(
            ui_aggregation, is_multiselect_chart_report)


class CasePropertyColumnOption(ColumnOption):

    def _get_datatype(self, ui_aggregation):
        """
        Return the data type that should be used for this property's indicator, given the aggregation that the
        user selected in the UI.
        """
        map = {
            UCR_AGG_SIMPLE: "string",
            UCR_AGG_EXPAND: "string",
            UCR_AGG_SUM: "decimal",
            UCR_AGG_AVG: "decimal",
        }
        return map[self._get_ucr_aggregation(ui_aggregation)]

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        column_id = get_column_name(self._property, suffix=self._get_datatype(ui_aggregation))
        return make_case_property_indicator(self._property, column_id, datatype=self._get_datatype(ui_aggregation))


class UsernameComputedCasePropertyOption(ColumnOption):
    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        column_id = get_column_name(self._property)
        expression = {
            'type': 'property_name',
            'property_name': 'user_id',
            'datatype': 'string',
        }
        if is_multiselect_chart_report:
            expression = {"type": "root_doc", "expression": expression}
        return {
            'datatype': 'string',
            'type': 'expression',
            'column_id': column_id,
            'expression': expression
        }

    def to_column_dicts(self, index, display_text, ui_aggregation, is_aggregated_on=False):
        column_dicts = super(UsernameComputedCasePropertyOption, self).to_column_dicts(
            index, display_text, ui_aggregation
        )
        column_dicts[0]['transform'] = {
            'type': 'custom',
            'custom_type': 'user_without_domain_display'
        }
        return column_dicts


class OwnernameComputedCasePropertyOption(ColumnOption):
    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        column_id = get_column_name(self._property)
        expression = {
            'type': 'property_name',
            'property_name': 'owner_id',
            'datatype': 'string',
        }
        if is_multiselect_chart_report:
            expression = {"type": "root_doc", "expression": expression}
        return {
            'datatype': 'string',
            'type': 'expression',
            'column_id': column_id,
            'expression': expression
        }

    def to_column_dicts(self, index, display_text, ui_aggregation, is_aggregated_on=False):
        column_dicts = super(OwnernameComputedCasePropertyOption, self).to_column_dicts(
            index, display_text, ui_aggregation
        )
        column_dicts[0]['transform'] = {
            'type': 'custom',
            'custom_type': 'owner_display'
        }
        return column_dicts


class CountColumn(ColumnOption):
    def __init__(self, default_display):
        super(CountColumn, self).__init__('computed/count', ["decimal"], default_display)

    def _get_ucr_aggregation(self, ui_aggregation):
        """
        Convert an aggregation value selected in the UI to and aggregation value to be used in the UCR
        configuration.
        :param ui_aggregation: UI aggregation value
        :return: UCR config aggregation value
        """
        return UCR_AGG_SUM

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        return {
            "column_id": "count",
            "display_name": "Count",
            "type": "boolean",
            "filter": {
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "constant",
                    "constant": 1
                },
                "property_value": 1
            }
        }

    def to_column_dicts(self, index, display_text, ui_aggregation, is_aggregated_on=False):
        column_dicts = super(CountColumn, self).to_column_dicts(index, display_text, ui_aggregation)
        del column_dicts[0]['transform']
        return column_dicts

    @property
    @memoized
    def aggregation_options(self):
        # The aggregation won't actually be used, but it will show up in the
        # "format" field of the report builder. We're hoping that "Count"
        # will make more sense to users than "Sum", which would technically
        # be more accurate.
        return ("Count",)


class RawPropertyColumnOption(ColumnOption):
    """
    Column option for raw properties (properties that just reference an existing data source)
    """

    def _get_indicator(self, ui_aggregation, is_multiselect_chart_report=False):
        return {
            "type": "expression",
            "column_id": self._property,
            "datatype": self._data_types[0],
            "display_name": self.get_property(),
            # "expression": expression,
        }
