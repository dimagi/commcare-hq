from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
from datetime import date
import hashlib

from dateutil.relativedelta import relativedelta
from django.utils.functional import cached_property
import six

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name
from custom.icds_reports.const import (
    AGG_COMP_FEEDING_TABLE,
    AGG_CCS_RECORD_CF_TABLE,
    AGG_CCS_RECORD_BP_TABLE,
    AGG_CCS_RECORD_PNC_TABLE,
    AGG_CCS_RECORD_THR_TABLE,
    AGG_CCS_RECORD_DELIVERY_TABLE,
    AGG_CHILD_HEALTH_PNC_TABLE,
    AGG_CHILD_HEALTH_THR_TABLE,
    AGG_DAILY_FEEDING_TABLE,
    AGG_GROWTH_MONITORING_TABLE,
    AGG_INFRASTRUCTURE_TABLE,
    AWW_INCENTIVE_TABLE,
    DASHBOARD_DOMAIN,
)
from six.moves import range
from six.moves import map


def transform_day_to_month(day):
    return day.replace(day=1)


def month_formatter(day):
    return transform_day_to_month(day).strftime('%Y-%m-%d')


class BaseICDSAggregationHelper(object):
    """Defines an interface for aggregating data from UCRs to specific tables
    for the dashboard.

    All aggregate tables are partitioned by state and month

    Attributes:
        ucr_data_source_id - The UCR data source that contains the raw data to aggregate
        aggregate_parent_table - The parent table defined in models.py that will contain aggregate data
        aggregate_child_table_prefix - The prefix for tables that inherit from the parent table
    """
    ucr_data_source_id = None
    aggregate_parent_table = None
    aggregate_child_table_prefix = None
    child_health_monthly_ucr_id = 'static-child_cases_monthly_tableau_v2'
    ccs_record_monthly_ucr_id = 'static-ccs_record_cases_monthly_tableau_v2'

    def __init__(self, state_id, month):
        self.state_id = state_id
        self.month = transform_day_to_month(month)

    @property
    def domain(self):
        # Currently its only possible for one domain to have access to the ICDS dashboard per env
        return DASHBOARD_DOMAIN

    @property
    def ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.ucr_data_source_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def generate_child_tablename(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        hash_for_table = hashlib.md5(self.state_id + month_string).hexdigest()[8:]
        return self.aggregate_child_table_prefix + hash_for_table

    def create_table_query(self, month=None):
        month = month or self.month
        month_string = month_formatter(month)
        tablename = self.generate_child_tablename(month)

        return """
        CREATE TABLE IF NOT EXISTS "{child_tablename}" (
            CHECK (month = %(month_string)s AND state_id = %(state_id)s),
            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
        ) INHERITS ("{parent_tablename}")
        """.format(
            parent_tablename=self.aggregate_parent_table,
            child_tablename=tablename,
        ), {
            "month_string": month_string,
            "state_id": self.state_id
        }

    def drop_table_query(self):
        tablename = self.generate_child_tablename(self.month)
        return 'DROP TABLE IF EXISTS "{tablename}"'.format(tablename=tablename)

    def data_from_ucr_query(self):
        """Returns (SQL query, query parameters) from the UCR data table that
        puts data in the form expected by the aggregate table
        """
        raise NotImplementedError

    def aggregate_query(self):
        """Returns (SQL query, query parameters) that will aggregate from a UCR
        source to an aggregate table.
        """
        raise NotImplementedError

    def compare_with_old_data_query(self):
        """Used for backend migrations from one data source to another. Returns
        (SQL query, query parameters) that will return any rows that are
        inconsistent from the old data to the new.
        """
        raise NotImplementedError


def recalculate_aggregate_table(model_class):
    """Expects a class (not instance) of models.Model

    Not expected to last past 2018 (ideally past May) so this shouldn't break in 2019
    """
    state_ids = (
        SQLLocation.objects
        .filter(domain='icds-cas', location_type__name='state')
        .values_list('location_id', flat=True)
    )

    for state_id in state_ids:
        for year in (2015, 2016, 2017):
            for month in range(1, 13):
                model_class.aggregate(state_id, date(year, month, 1))

        for month in range(1, date.today().month + 1):
            model_class.aggregate(state_id, date(2018, month, 1))


class AwcInfrastructureAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-infrastructure_form_v2'
    aggregate_parent_table = AGG_INFRASTRUCTURE_TABLE
    aggregate_child_table_prefix = 'icds_db_infra_form_'
    column_names = (
        'timeend',
        'awc_building', 'source_drinking_water', 'toilet_functional',
        'electricity_awc', 'adequate_space_pse',
        'adult_scale_available', 'baby_scale_available', 'flat_scale_available',
        'adult_scale_usable', 'baby_scale_usable', 'cooking_utensils_usable',
        'infantometer_usable', 'medicine_kits_usable', 'stadiometer_usable',
    )

    def _window_helper(self, column_name):
        return (
            "LAST_VALUE({column}) OVER {column} AS {column}".format(column=column_name),
            """
            {column} AS (
                PARTITION BY awc_id
                ORDER BY
                    CASE WHEN {column} IS NULL THEN 0 ELSE 1 END ASC,
                    timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            )
            """.format(column=column_name)
        )

    def data_from_ucr_query(self):
        next_month_start = month_formatter(self.month + relativedelta(months=1))
        six_months_ago = month_formatter(self.month - relativedelta(months=6))

        windows = [
            self._window_helper(column_name)
            for column_name in self.column_names
        ]
        select_lines = ', '.join([window[0] for window in windows])
        window_lines = ', '.join([window[1] for window in windows])

        return """
            SELECT
                DISTINCT awc_id AS awc_id,
                {select_lines}
            FROM "{ucr_tablename}"
            WHERE timeend >= %(six_months_ago)s AND timeend < %(next_month_start)s
                AND state_id = %(state_id)s AND awc_id IS NOT NULL
            WINDOW
                {window_lines}
        """.format(
            ucr_tablename=self.ucr_tablename,
            select_lines=select_lines,
            window_lines=window_lines,
        ), {
            "six_months_ago": six_months_ago,
            "next_month_start": next_month_start,
            "state_id": self.state_id,
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        return """
        INSERT INTO "{tablename}" (
            state_id, month, awc_id, latest_time_end_processed,
            awc_building, source_drinking_water, toilet_functional,
            electricity_awc, adequate_space_pse,
            adult_scale_available, baby_scale_available, flat_scale_available,
            adult_scale_usable, baby_scale_usable, cooking_utensils_usable,
            infantometer_usable, medicine_kits_usable, stadiometer_usable
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            ucr.awc_id AS awc_id,
            ucr.timeend as latest_time_end_processed,
            ucr.awc_building as awc_building,
            ucr.source_drinking_water as source_drinking_water,
            ucr.toilet_functional as toilet_functional,
            ucr.electricity_awc as electricity_awc,
            ucr.adequate_space_pse as adequate_space_pse,
            ucr.adult_scale_available as adult_scale_available,
            ucr.baby_scale_available as baby_scale_available,
            ucr.flat_scale_available as flat_scale_available,
            ucr.adult_scale_usable as adult_scale_usable,
            ucr.baby_scale_usable as baby_scale_usable,
            ucr.cooking_utensils_usable as cooking_utensils_usable,
            ucr.infantometer_usable as infantometer_usable,
            ucr.medicine_kits_usable as medicine_kits_usable,
            ucr.stadiometer_usable as stadiometer_usable
          FROM ({ucr_table_query}) ucr
        )
        """.format(
            ucr_table_query=ucr_query,
            tablename=tablename
        ), query_params


class AwwIncentiveAggregationHelper(BaseICDSAggregationHelper):
    aggregate_parent_table = AWW_INCENTIVE_TABLE
    aggregate_child_table_prefix = 'icds_db_aww_incentive_'

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)

        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }

        return """
        INSERT INTO "{tablename}" (
            state_id, month, awc_id, block_id, state_name, district_name, block_name, 
            supervisor_name, awc_name, aww_name, contact_phone_number, wer_weighed,
            wer_eligible, awc_num_open, valid_visits, expected_visits
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            awc_id,
            block_id,
            state_name,
            district_name,
            block_name,
            supervisor_name,
            awc_name,
            aww_name,
            contact_phone_number,
            wer_weighed,
            wer_eligible,
            awc_num_open,
            valid_visits,
            expected_visits
          FROM agg_ccs_record_monthly AS acm
          WHERE acm.month = %(month)s AND acm.state_id = %(state_id)s and aggregation_level=5
        )
        """.format(
            tablename=tablename
        ), query_params
