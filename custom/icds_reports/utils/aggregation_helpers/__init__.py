from __future__ import absolute_import
from __future__ import unicode_literals


def transform_day_to_month(day):
    return day.replace(day=1)


def month_formatter(day):
    return transform_day_to_month(day).strftime('%Y-%m-%d')


def date_to_string(date):
    return date.strftime('%Y-%m-%d')


class AggregationHelper(object):
    """Base class used to tag aggregation helpers for monolithic postgres

    Adding a new helper class:
    1. Create the class, both monolith and distributed
    2. Update the imports in ../monolith/__init__.py and ../distributed/__init__.py
    3. Update helpers.py to add the new helper to the `HELPERS` list
    """
    helper_key = None  # must match the corresponding key on the distributed helper
