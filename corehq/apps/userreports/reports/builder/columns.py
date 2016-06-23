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
        self.is_non_numeric = is_non_numeric

    def to_column_dict(self, index, display_text, aggregation):
        return {
            "format": "default",
            "aggregation": self.aggregation_map[aggregation],
            "field": self.indicator_id,
            "column_id": "column_{}".format(index),
            "type": "field",
            "display": display_text,
            "transform": {'type': 'custom', 'custom_type': 'short_decimal_display'},
        }


class QuestionColumnOption(ColumnOption):
    def __init__(self, id, display, indicator_id, is_non_numeric, question_source):
        super(QuestionColumnOption, self).__init__(id, display, indicator_id, is_non_numeric)
        self.question_source = question_source


class CountColumn(ColumnOption):
    def __init__(self, display):
        super(CountColumn, self).__init__('computed/count', display, "count", False)

    def to_column_dict(self, index, display_text, aggregation):
        return {
            'type': 'field',
            'format': 'default',
            'aggregation': 'sum',
            'field': 'count',
            'column_id': 'column_{}'.format(index),
            'display': display_text,
        }
