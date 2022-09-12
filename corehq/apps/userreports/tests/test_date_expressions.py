from datetime import date, datetime

from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import FactoryContext
from corehq.util.test_utils import generate_cases


@generate_cases([
    ({'dob': '2015-01-20'}, 1, date(2015, 2, 20)),
    ({'dob': '2015-01-20'}, 3, date(2015, 4, 20)),
    ({'dob': '2015-12-20'}, 3, date(2016, 3, 20)),
    ({'dob': date(2015, 1, 31)}, 1, date(2015, 2, 28)),
    ({'dob': date(2015, 2, 28)}, -1, date(2015, 1, 28)),
    ({'dob': date(2015, 1, 31)}, -2, date(2014, 11, 30)),
    ({'dob': datetime(2015, 1, 20)}, 3, date(2015, 4, 20)),
    ({'dob': datetime(2015, 1, 20)}, 3.0, date(2015, 4, 20)),
    ({'dob': datetime(2015, 1, 20)}, '3.0', date(2015, 4, 20)),
    (
        {'dob': datetime(2015, 1, 20), 'months': '3'},
        {'type': 'property_name', 'property_name': 'months'},
        date(2015, 4, 20)
    ),
])
def test_add_months_to_date_expression(self, source_doc, months_expression, expected_value):
    expression = ExpressionFactory.from_spec({
        'type': 'add_months',
        'date_expression': {
            'type': 'property_name',
            'property_name': 'dob',
        },
        'months_expression': months_expression
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({'dob': '2015-01-20'}, date(2015, 1, 1)),
    ({'dob': date(2015, 1, 31)}, date(2015, 1, 1)),
    ({'dob': datetime(2015, 1, 20)}, date(2015, 1, 1)),
])
def test_month_start_date_expression(self, source_doc, expected_value):
    expression = ExpressionFactory.from_spec({
        'type': 'month_start_date',
        'date_expression': {
            'type': 'property_name',
            'property_name': 'dob',
        },
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({'dob': '2015-01-20'}, date(2015, 1, 31)),
    ({'dob': date(2015, 2, 20)}, date(2015, 2, 28)),
    ({'dob': datetime(2015, 4, 20)}, date(2015, 4, 30)),
])
def test_month_end_date_expression(self, source_doc, expected_value):
    expression = ExpressionFactory.from_spec({
        'type': 'month_end_date',
        'date_expression': {
            'type': 'property_name',
            'property_name': 'dob',
        },
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({'dob': '2015-01-20'}, '2015-02-20', 31),
    ({'dob': '2015-01-20'}, '2015-04-20', 90),
    ({'dob': '2015-02-20'}, '2015-01-20', -31),
    (
        {'dob': date(2015, 1, 31), 'to_date': '2015-02-28'},
        {'type': 'property_name', 'property_name': 'to_date'},
        28
    ),
])
def test_diff_days_expression(self, source_doc, to_date_expression, expected_value):
    from_date_expression = {
        'type': 'property_name',
        'property_name': 'dob',
    }
    expression = ExpressionFactory.from_spec({
        'type': 'diff_days',
        'from_date_expression': from_date_expression,
        'to_date_expression': to_date_expression
    })
    self.assertEqual(expected_value, expression(source_doc))

    # test named_expression for 'from_date_expression'
    context = FactoryContext(
        {"from_date_name": ExpressionFactory.from_spec(from_date_expression)},
        {}
    )
    named_expression = ExpressionFactory.from_spec({
        'type': 'diff_days',
        'from_date_expression': {
            "type": "named",
            "name": "from_date_name"
        },
        'to_date_expression': to_date_expression
    }, context)
    self.assertEqual(expected_value, named_expression(source_doc))


@generate_cases([
    ({'dob': '2015-01-20'}, 3, date(2015, 1, 23)),
    ({'dob': '2015-01-20'}, 5, date(2015, 1, 25)),
    ({'dob': date(2015, 1, 20)}, 3, date(2015, 1, 23)),
    ({'dob': datetime(2015, 1, 20)}, 3, date(2015, 1, 23)),
    ({'dob': datetime(2015, 1, 20)}, 3.0, date(2015, 1, 23)),
    ({'dob': datetime(2015, 1, 20)}, '3.0', date(2015, 1, 23)),
    (
        {'dob': datetime(2015, 1, 20), 'days': '3'},
        {'type': 'property_name', 'property_name': 'days'},
        date(2015, 1, 23)
    ),
])
def test_add_days_to_date_expression(self, source_doc, count_expression, expected_value):
    expression = ExpressionFactory.from_spec({
        'type': 'add_days',
        'date_expression': {
            'type': 'property_name',
            'property_name': 'dob',
        },
        'count_expression': count_expression
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({'visit_date': '2020-03-12T20:33:49Z'}, 2, datetime(2020, 3, 12, 22, 33, 49)),
    # 3 hours in UTC due to time zone change
    ({'visit_date': '2020-03-12T20:33:49.134+02'}, 5, datetime(2020, 3, 12, 23, 33, 49, 134000)),
    # 7 hours in UTC due to time zone change
    ({'visit_date': '2020-03-12T20:33:49.134-02'}, 5, datetime(2020, 3, 13, 3, 33, 49, 134000)),
    ({'visit_date': '2020-03-12T20:33:49.134000Z'}, 2, datetime(2020, 3, 12, 22, 33, 49, 134000)),
    ({'visit_date': datetime(2020, 3, 12, 20, 33, 49)}, 2, datetime(2020, 3, 12, 22, 33, 49)),
    (
        {'visit_date': datetime(2020, 3, 12, 20, 33, 49), 'hours': '3'},
        {'type': 'property_name', 'property_name': 'hours'},
        datetime(2020, 3, 12, 23, 33, 49)),
])
def test_add_hours_to_datetime_expression(self, source_doc, count_expression, expected_value):
    expression = ExpressionFactory.from_spec({
        'type': 'add_hours',
        'date_expression': {
            'type': 'property_name',
            'property_name': 'visit_date',
        },
        'count_expression': count_expression
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({'dob': '2015-01-20'}, date(2022, 9, 30)),
    ({'dob': '2014-13-05'}, date(2022, 9, 10)),
    ({'dob': date(2015, 1, 20)}, date(2022, 9, 30)),
    ({'dob': datetime(2015, 1, 20)}, date(2022, 9, 30)),
])
def test_ethiopian_to_gregorian_expression(self, source_doc, expected_value):
    date_expression = {
        'type': 'property_name',
        'property_name': 'dob',
    }
    expression = ExpressionFactory.from_spec({
        'type': 'ethiopian_date_to_gregorian_date',
        'date_expression': date_expression,
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({"type": "constant", "constant": '2015-01-20'}, date(2022, 9, 30)),  # Date that looks like gregorian dates
    ({"type": "constant", "constant": '2014-13-05'}, date(2022, 9, 10)),  # Invalid gregorian date, valid ethiopian
])
def test_ethiopian_to_gregorian_expression_constant(self, expression, expected_value):
    """
        Used to fail with BadValueError: datetime.date(2020, 9, 9) is not a date-formatted string
    """
    wrapped_expression = ExpressionFactory.from_spec({
        'type': 'ethiopian_date_to_gregorian_date',
        'date_expression': expression,
    })
    self.assertEqual(expected_value, wrapped_expression({"foo": "bar"}))


@generate_cases([
    ({'dob': '2022-09-30'}, '2015-01-20'),
    ({'dob': date(2022, 9, 30)}, '2015-01-20'),
    ({'dob': datetime(2022, 9, 30)}, '2015-01-20'),
])
def test_gregorian_to_ethiopian_expression(self, source_doc, expected_value):
    date_expression = {
        'type': 'property_name',
        'property_name': 'dob',
    }
    expression = ExpressionFactory.from_spec({
        'type': 'gregorian_date_to_ethiopian_date',
        'date_expression': date_expression,
    })
    self.assertEqual(expected_value, expression(source_doc))


@generate_cases([
    ({"type": "constant", "constant": '2021-10-11'}, '2014-02-01'),
    ({"type": "constant", "constant": '2021-10-9'}, '2014-01-29'),
])
def test_gregorian_to_ethiopian_expression_constant(self, expression, expected_value):
    """
        Used to fail with BadValueError: datetime.date(2020, 9, 9) is not a date-formatted string
    """
    wrapped_expression = ExpressionFactory.from_spec({
        'type': 'gregorian_date_to_ethiopian_date',
        'date_expression': expression,
    })
    self.assertEqual(expected_value, wrapped_expression({"foo": "bar"}))
