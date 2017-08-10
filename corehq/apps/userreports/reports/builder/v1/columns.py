
from dimagi.utils.decorators.memoized import memoized


class ColumnOption(object):
    """
    This class represents column options in the report builder.
    """
    aggregation_map = {
        'simple': 'simple',
        'Count per Choice': 'expand',
        'Sum': 'sum',
        'Average': 'avg'
    }

    def __init__(self, id, display, indicator_id, is_non_numeric):
        self.id = id  # The string representing this choice in the configure report form.
        self.display = display
        self.indicator_id = indicator_id
        self._is_non_numeric = is_non_numeric

    def to_dict(self):
        dict_representation = {}
        dict_representation.update(self.__dict__)
        dict_representation['aggregation_options'] = self.aggregation_options
        return dict_representation

    @property
    @memoized
    def aggregation_options(self):
        if self._is_non_numeric:
            return ("Count per Choice",)
        return ("Count per Choice", "Sum", "Average")

    def to_column_dicts(self, index, display_text, aggregation, is_aggregated_on=False):
        return [{
            "format": "default",
            "aggregation": self.aggregation_map[aggregation],
            "field": self.indicator_id,
            "column_id": "column_{}".format(index),
            "type": "field",
            "display": display_text,
            "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'},
        }]


class QuestionColumnOption(ColumnOption):
    def __init__(self, id, display, indicator_id, is_non_numeric, question_source):
        super(QuestionColumnOption, self).__init__(id, display, indicator_id, is_non_numeric)
        self.question_source = question_source


class MultiselectQuestionColumnOption(QuestionColumnOption):
    LABEL_DIVIDER = " - "

    def __init__(self, id, display, indicator_id, question_source):
        super(QuestionColumnOption, self).__init__(id, display, indicator_id, False)
        self.question_source = question_source

    def to_column_dicts(self, index, display_text, aggregation, is_aggregated_on=False):
        assert aggregation in ["Count per Choice", "simple"]

        if is_aggregated_on:
            return super(MultiselectQuestionColumnOption, self).to_column_dicts(
                index, display_text, aggregation, is_aggregated_on=False
            )

        columns = []
        for choice_index, choice in enumerate(self.question_source['options']):
            columns.append({
                "type": "field",
                "column_id": "column_{}_{}".format(index, choice_index),
                "format": "default",
                "aggregation": "sum",
                "field": "{}_{}".format(self.indicator_id, choice['value']),
                "display": display_text + self.LABEL_DIVIDER + choice['label']
            })

        return columns

    @property
    @memoized
    def aggregation_options(self):
        return ("Count per Choice",)


class CountColumn(ColumnOption):
    def __init__(self, display):
        super(CountColumn, self).__init__('computed/count', display, "count", False)

    @property
    @memoized
    def aggregation_options(self):
        # The aggregation won't actually be used, but it will show up in the
        # "format" field of the report builder. We're hoping that "Count"
        # will make more sense to users than "Sum", which would technically
        # be more accurate.
        return ("Count",)

    def to_column_dicts(self, index, display_text, aggregation, is_aggregated_on=False):
        # aggregation is only an arg so that we match the the parent's method signature.
        column_dicts = super(CountColumn, self).to_column_dicts(index, display_text, "Sum")
        del column_dicts[0]['transform']
        return column_dicts
