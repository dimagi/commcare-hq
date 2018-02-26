from __future__ import absolute_import
from __future__ import unicode_literals
import hashlib

from dateutil.relativedelta import relativedelta
from toggle.models import Toggle

from corehq.apps.userreports.models import StaticDataSourceConfiguration, get_datasource_config
from corehq.apps.userreports.util import get_table_name


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

    def __init__(self, state_id, month):
        self.state_id = state_id
        self.month = transform_day_to_month(month)

    @property
    def domain(self):
        # Currently its only possible for one domain to have access to the ICDS dashboard per env
        return Toggle.get('dashboard_icds_reports').enabled_users[0][len('domain:'):]

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


class ComplementaryFormsAggregationHelper(BaseICDSAggregationHelper):
    ucr_data_source_id = 'static-complementary_feeding_forms'
    aggregate_parent_table = 'icds_dashboard_comp_feed_form'
    aggregate_child_table_prefix = 'icds_db_child_cf_form_'

    @property
    def _old_ucr_tablename(self):
        doc_id = StaticDataSourceConfiguration.get_doc_id(self.domain, self.child_health_monthly_ucr_id)
        config, _ = get_datasource_config(doc_id, self.domain)
        return get_table_name(self.domain, config.table_id)

    def data_from_ucr_query(self):
        current_month_start = month_formatter(self.month)
        next_month_start = month_formatter(self.month + relativedelta(months=1))

        return """
        SELECT DISTINCT child_health_case_id AS case_id,
        LAST_VALUE(timeend) OVER w AS latest_time_end,
        MAX(play_comp_feeding_vid) OVER w AS play_comp_feeding_vid,
        MAX(comp_feeding) OVER w AS comp_feeding_ever,
        MAX(demo_comp_feeding) OVER w AS demo_comp_feeding,
        MAX(counselled_pediatric_ifa) OVER w AS counselled_pediatric_ifa,
        LAST_VALUE(comp_feeding) OVER w AS comp_feeding_latest,
        LAST_VALUE(diet_diversity) OVER w AS diet_diversity,
        LAST_VALUE(diet_quantity) OVER w AS diet_quantity,
        LAST_VALUE(hand_wash) OVER w AS hand_wash
        FROM "{ucr_tablename}"
        WHERE timeend >= %(current_month_start)s AND timeend < %(next_month_start)s AND state_id = %(state_id)s
        WINDOW w AS (
            PARTITION BY child_health_case_id
            ORDER BY timeend RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        )
        """.format(ucr_tablename=self.ucr_tablename), {
            "current_month_start": current_month_start,
            "next_month_start": next_month_start,
            "state_id": self.state_id
        }

    def aggregation_query(self):
        month = self.month.replace(day=1)
        tablename = self.generate_child_tablename(month)
        previous_month_tablename = self.generate_child_tablename(month - relativedelta(months=1))

        ucr_query, ucr_query_params = self.data_from_ucr_query()
        query_params = {
            "month": month_formatter(month),
            "state_id": self.state_id
        }
        query_params.update(ucr_query_params)

        # GREATEST calculations are for when we want to know if a thing has
        # ever happened to a case.
        # CASE WHEN calculations are for when we want to know if a case
        # happened during the last form for this case. We must use CASE WHEN
        # and not COALESCE as when questions are skipped they will be NULL
        # and we want NULL in the aggregate table
        return """
        INSERT INTO "{tablename}" (
          state_id, month, case_id, latest_time_end_processed, comp_feeding_ever,
          demo_comp_feeding, counselled_pediatric_ifa, play_comp_feeding_vid,
          comp_feeding_latest, diet_diversity, diet_quantity, hand_wash
        ) (
          SELECT
            %(state_id)s AS state_id,
            %(month)s AS month,
            COALESCE(ucr.case_id, prev_month.case_id) AS case_id,
            GREATEST(ucr.latest_time_end, prev_month.latest_time_end_processed) AS latest_time_end_processed,
            GREATEST(ucr.comp_feeding_ever, prev_month.comp_feeding_ever) AS comp_feeding_ever,
            GREATEST(ucr.demo_comp_feeding, prev_month.demo_comp_feeding) AS demo_comp_feeding,
            GREATEST(ucr.counselled_pediatric_ifa, prev_month.counselled_pediatric_ifa) AS counselled_pediatric_ifa,
            GREATEST(ucr.play_comp_feeding_vid, prev_month.play_comp_feeding_vid) AS play_comp_feeding_vid,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.comp_feeding_latest ELSE prev_month.comp_feeding_latest
            END AS comp_feeding_latest,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.diet_diversity ELSE prev_month.diet_diversity
            END AS diet_diversity,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.diet_quantity ELSE prev_month.diet_quantity
            END AS diet_quantity,
            CASE WHEN ucr.latest_time_end IS NOT NULL
                 THEN ucr.hand_wash ELSE prev_month.hand_wash
            END AS hand_wash
          FROM ({ucr_table_query}) ucr
          FULL OUTER JOIN "{previous_month_tablename}" prev_month
          ON ucr.case_id = prev_month.case_id
        )
        """.format(
            ucr_table_query=ucr_query,
            previous_month_tablename=previous_month_tablename,
            tablename=tablename
        ), query_params

    def compare_with_old_data_query(self):
        """Compares data from the complementary feeding forms aggregate table
        to the the old child health monthly UCR table that current aggregate
        script uses
        """
        month = self.month.replace(day=1)
        return """
        SELECT agg.case_id
        FROM "{child_health_monthly_ucr}" chm_ucr
        FULL OUTER JOIN "{new_agg_table}" agg
        ON chm_ucr.doc_id = agg.case_id AND chm_ucr.month = agg.month AND agg.state_id = chm_ucr.state_id
        WHERE chm_ucr.month = %(month)s and agg.state_id = %(state_id)s AND (
              (chm_ucr.cf_eligible = 1 AND (
                  chm_ucr.cf_in_month != agg.comp_feeding_latest OR
                  chm_ucr.cf_diet_diversity != agg.diet_diversity OR
                  chm_ucr.cf_diet_quantity != agg.diet_quantity OR
                  chm_ucr.cf_handwashing != agg.hand_wash OR
                  chm_ucr.cf_demo != agg.demo_comp_feeding OR
                  chm_ucr.counsel_pediatric_ifa != agg.counselled_pediatric_ifa OR
                  chm_ucr.counsel_comp_feeding_vid != agg.play_comp_feeding_vid
              )) OR (chm_ucr.cf_initiation_eligible = 1 AND chm_ucr.cf_initiated != agg.comp_feeding_ever)
        )
        """.format(
            child_health_monthly_ucr=self._old_ucr_tablename,
            new_agg_table=self.aggregate_parent_table,
        ), {
            "month": month.strftime('%Y-%m-%d'),
            "state_id": self.state_id
        }
