from __future__ import absolute_import
from corehq.apps.userreports.reports.builder import (
    make_form_meta_block_indicator,
    make_case_property_indicator,
    make_form_question_indicator,
    make_multiselect_question_indicator,
)
from corehq.apps.userreports.reports.builder.const import (
    AGGREGATION_COUNT_PER_CHOICE,
    AGGREGATION_AVERAGE,
    AGGREGATION_GROUP_BY,
    AGGREGATION_SUM,
    AGGREGATION_SIMPLE,
    AGGREGATION_COUNT,
    AGGREGATION_ID_MAP,
    UCR_REPORT_AGGREGATION_SIMPLE,
    UCR_REPORT_AGGREGATION_SUM,
    UCR_REPORT_AGGREGATION_EXPAND,
    UCR_REPORT_AGGREGATION_AVG,
)
from corehq.apps.userreports.sql import get_column_name
from dimagi.utils.decorators.memoized import memoized
import six


def _get_column_name_with_value(column_name, value):
    value = value.encode('unicode-escape')
    value_hash = hashlib.sha1(value).hexdigest()[:8]
    return "{}_{}".format(column_name, value_hash)


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
        if "decimal" in self._data_types:
            return (AGGREGATION_GROUP_BY,
                    AGGREGATION_COUNT_PER_CHOICE,
                    AGGREGATION_SUM,
                    AGGREGATION_AVERAGE,
                    AGGREGATION_ID_MAP)
        else:
            return (AGGREGATION_GROUP_BY, AGGREGATION_COUNT_PER_CHOICE, AGGREGATION_ID_MAP)

    def _get_aggregation_config(self, agg):
        """
        Convert an aggregation value selected in the UI to and aggregation value to be used in the UCR
        configuration.
        :param agg: UI aggregation value
        :return: UCR config aggregation value
        """
        aggregation_map = {
            AGGREGATION_SIMPLE: UCR_REPORT_AGGREGATION_SIMPLE,
            AGGREGATION_COUNT_PER_CHOICE: UCR_REPORT_AGGREGATION_EXPAND,
            AGGREGATION_SUM: UCR_REPORT_AGGREGATION_SUM,
            AGGREGATION_AVERAGE: UCR_REPORT_AGGREGATION_AVG,
            AGGREGATION_GROUP_BY: UCR_REPORT_AGGREGATION_SIMPLE,
            AGGREGATION_ID_MAP: UCR_REPORT_AGGREGATION_SUM,
            None: UCR_REPORT_AGGREGATION_SIMPLE,
        }
        return aggregation_map[agg]

    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
        """
        Get the indicator corresponding to this column option. This function will raise an exception if more than
        one indicator corresponds to this column.
        """
        raise NotImplementedError

    def get_indicators(self, aggregation, calculation_config=None, is_multiselect_chart_report=False):
        """
        Return the indicators corresponding to this column option.
        """

        # Generate multiple columns for the ID map
        if aggregation == AGGREGATION_ID_MAP:
            # This is in the format value: display_name
            id_map = calculation_config or {}
            indicator = self.get_indicator(aggregation,
                                           is_multiselect_chart_report=is_multiselect_chart_report)
            base_boolean_indicator = {
                "column_id": indicator['column_id'],
                "type": "boolean",
                "filter": {
                    "type": "boolean_expression",
                    "operator": "in_multi",
                    "expression": indicator['expression'],
                    "property_value": None
                }
            }

            indicators = []
            for value in id_map.keys():
                i = base_boolean_indicator.copy()
                i['column_id'] = _get_column_name_with_value(i['column_id'], value)
                i['filter']['property_value'] = value
                indicators.append(i)
            return indicators

        return [self.get_indicator(aggregation)]

    def to_column_dicts(self, index, display_text, aggregation, calculation_config=None, is_aggregated_on=False):
        """
        Return a UCR report column configuration dictionary
        :param index: The index of the column in the list of columns, e.g. 0, 1, 2, etc.
        :param display_text: The label for this column
        :param aggregation: What sort of aggregation the user selected for this column in the UI
        :param is_aggregated_on: True if the user chose to "group by" this column
        :return:
        """

        # Generate multiple report columns for the ID map
        if aggregation == AGGREGATION_ID_MAP:
            # This is in the format {value: display_name}
            id_map = calculation_config or {}
            indicator = self.get_indicator(aggregation)
            base_report_column = {
                "format": "default",
                "aggregation": self._get_aggregation_config(aggregation),
                "field": "",
                "column_id": "",
                "type": "field",
                "display": "",
                "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'},
            }

            cols = []
            for i, value in id_map.keys():
                col = base_report_column.copy()
                col['display'] = id_map[value]
                col["column_id"] = "column_{}_{}".format(index, i)
                col["field"] = _get_column_name_with_value(indicator['column_id'], value)
                cols.append(col)
            return cols

        return [{
            "format": "default",
            "aggregation": self._get_aggregation_config(aggregation),
            "field": self.get_indicator(aggregation)['column_id'],
            "column_id": "column_{}".format(index),
            "type": "field",
            "display": display_text,
            "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'},
        }]

    def to_report_aggregation_list(self, aggregation):
        """
        Returns the report aggregation list for this column
        :param aggregation:
        :return: list of strings
        """
        if aggregation == AGGREGATION_GROUP_BY:
            return [self.get_indicator(aggregation)['column_id']]
        return []

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

    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
        if aggregation not in self.aggregation_options:
            raise Exception("invalid aggregation option: {}".format(aggregation))

        if aggregation in (AGGREGATION_SUM, AGGREGATION_AVERAGE):
            data_type = "decimal"
        else:
            data_type = None  # use the default

        column_id = get_column_name(self._property.strip("/"))
        if data_type:
            column_id += ("_" + data_type)
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

    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
        # aggregation parameter is never used because we need not infer the data type
        # self._question_source is a tuple of (identifier, datatype)
        identifier = self._meta_property_spec[0]
        if isinstance(identifier, six.string_types):
            identifier = [identifier]
        identifier = "/".join(identifier)
        column_id = get_column_name(identifier.strip("/"))
        return make_form_meta_block_indicator(
            self._meta_property_spec, column_id, root_doc=is_multiselect_chart_report
        )

    @property
    def aggregation_options(self):
        if "decimal" in self._data_types:
            return (AGGREGATION_GROUP_BY,
                    AGGREGATION_COUNT_PER_CHOICE,
                    AGGREGATION_SUM,
                    AGGREGATION_AVERAGE)
        else:
            return (AGGREGATION_GROUP_BY, AGGREGATION_COUNT_PER_CHOICE)


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

    def to_column_dicts(self, index, display_text, aggregation, calculation_config=None, is_aggregated_on=False):
        assert aggregation in [AGGREGATION_COUNT_PER_CHOICE, AGGREGATION_SIMPLE]

        if is_aggregated_on:
            return [{
                "format": "default",
                "aggregation": self._get_aggregation_config(aggregation),
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
                "aggregation": UCR_REPORT_AGGREGATION_SUM,
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
        # TODO: Is it a problem that this is the same as the filter/agg indicator id?
        column_id = get_column_name(self._property.strip("/"))
        return make_multiselect_question_indicator(self._question_source, column_id)

    def get_indicators(self, aggregation, calculation_config=None, is_multiselect_chart_report=False):
        return [self._get_filter_and_agg_indicator(), self._get_choice_indicator()]

    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
        if aggregation == AGGREGATION_GROUP_BY:
            return super(MultiselectQuestionColumnOption, self).get_indicator(
                aggregation, is_multiselect_chart_report)
        else:
            raise Exception(
                "This column option is represented by multiple indicators when not being aggreated by, "
                "use get_indicators() instead (aggregation was {})".format(aggregation)
            )


class CasePropertyColumnOption(ColumnOption):

    def _get_datatype(self, aggregation):
        """
        Return the data type that should be used for this property's indicator, given the aggregation that the
        user selected in the UI.
        """
        map = {
            UCR_REPORT_AGGREGATION_SIMPLE: "string",
            UCR_REPORT_AGGREGATION_EXPAND: "string",
            UCR_REPORT_AGGREGATION_SUM: "decimal",
            UCR_REPORT_AGGREGATION_AVG: "decimal",
        }
        return map[self._get_aggregation_config(aggregation)]

    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
        column_id = get_column_name(self._property) + "_" + self._get_datatype(aggregation)
        return make_case_property_indicator(self._property, column_id, datatype=self._get_datatype(aggregation))


class UsernameComputedCasePropertyOption(ColumnOption):
    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
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

    def to_column_dicts(self, index, display_text, aggregation, calculation_config=None, is_aggregated_on=False):
        column_dicts = super(UsernameComputedCasePropertyOption, self).to_column_dicts(
            index, display_text, aggregation, calculation_config=calculation_config
        )
        column_dicts[0]['transform'] = {
            'type': 'custom',
            'custom_type': 'user_without_domain_display'
        }
        return column_dicts

    @property
    def aggregation_options(self):
        return (AGGREGATION_GROUP_BY,)

class OwnernameComputedCasePropertyOption(ColumnOption):
    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
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

    def to_column_dicts(self, index, display_text, aggregation, calculation_config=None, is_aggregated_on=False):
        column_dicts = super(OwnernameComputedCasePropertyOption, self).to_column_dicts(
            index, display_text, aggregation, calculation_config=calculation_config
        )
        column_dicts[0]['transform'] = {
            'type': 'custom',
            'custom_type': 'owner_display'
        }
        return column_dicts

    @property
    def aggregation_options(self):
        return (AGGREGATION_GROUP_BY,)


class CountColumn(ColumnOption):
    def __init__(self, default_display):
        super(CountColumn, self).__init__('computed/count', ["decimal"], default_display)

    def _get_aggregation_config(self, agg):
        """
        Convert an aggregation value selected in the UI to and aggregation value to be used in the UCR
        configuration.
        :param agg: UI aggregation value
        :return: UCR config aggregation value
        """
        return UCR_REPORT_AGGREGATION_SUM

    def get_indicator(self, aggregation, is_multiselect_chart_report=False):
        return {
            "display_name": "Count",
            "type": "count",
            "column_id": "count"
        }

    def to_column_dicts(self, index, display_text, aggregation, calculation_config=None, is_aggregated_on=False):
        column_dicts = super(CountColumn, self).to_column_dicts(index, display_text, aggregation,
                                                                calculation_config=calculation_config)
        del column_dicts[0]['transform']
        return column_dicts

    @property
    @memoized
    def aggregation_options(self):
        # The aggregation won't actually be used, but it will show up in the
        # "format" field of the report builder. We're hoping that "Count"
        # will make more sense to users than "Sum", which would technically
        # be more accurate.
        return (AGGREGATION_COUNT,)
