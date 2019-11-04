from datetime import date, timedelta


def transform_day_to_month(day):
    return day.replace(day=1)


def month_formatter(day):
    return transform_day_to_month(day).strftime('%Y-%m-%d')


def date_to_string(date):
    return date.strftime('%Y-%m-%d')


class AggregationHelper(object):
    """Base class used to tag aggregation helpers

    Adding a new helper class:
    1. Create the class
    2. Update the imports in ../distributed/__init__.py
    3. Update helpers.py to add the new helper to the `HELPERS` list
    """
    helper_key = None  # must match the corresponding key on the distributed helper


def previous_month_aggregation_should_run(day: date) -> bool:
    if date.day in (1, 2, 3):
        return True
    if date.day == 11:  # for performance report
        return True
    if date.isoweekday == 6:  # Saturday
        return True
    if date.month != (date + timedelta(days=1)).month:  # last day of month
        return True

    return False
