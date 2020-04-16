from datetime import date


def transform_day_to_month(day):
    return day.replace(day=1)


def month_formatter(day):
    return transform_day_to_month(day).strftime('%Y-%m-%d')


def date_to_string(date):
    return date.strftime('%Y-%m-%d')


def get_child_health_tablename(month):
    from custom.icds_reports.utils.aggregation_helpers.distributed import ChildHealthMonthlyAggregationDistributedHelper
    base_tablename = ChildHealthMonthlyAggregationDistributedHelper.base_tablename
    month_string = month.strftime("%Y-%m-%d")
    return f"{base_tablename}_{month_string}"


def get_child_health_temp_tablename(month):
    tablename = get_child_health_tablename(month)
    return f"tmp_{tablename}"


def get_agg_child_temp_tablename():
    return 'tmp_agg_child_health_5'


def get_prev_agg_tablename(table_alias):
    return f'{table_alias}_prev'


def is_current_month(month):
    return month == transform_day_to_month(date.today())


class AggregationHelper(object):
    """Base class used to tag aggregation helpers

    Adding a new helper class:
    1. Create the class
    2. Update the imports in ../distributed/__init__.py
    3. Update helpers.py to add the new helper to the `HELPERS` list
    """
    helper_key = None  # must match the corresponding key on the distributed helper
