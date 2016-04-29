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
