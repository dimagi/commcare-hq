from datetime import timedelta
from django.db.models import Max

import re

from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from custom.icds_reports.const import  AGG_DASHBOARD_ACTIVITY
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_id_username_pairs_by_domain
from django.utils.functional import cached_property
from corehq.apps.users.models import CommCareUser


class DashboardActivityReportAggregate(BaseICDSAggregationDistributedHelper):
    aggregate_parent_table = AGG_DASHBOARD_ACTIVITY

    def __init__(self, date):
        self.date = date
        self.last_agg_date = self.get_last_agg_date()

    def aggregate(self, cursor):
        cursor.execute(self.drop_table_query())
        cursor.execute(*self.create_table_query())
        add_query, add_params = self.add_missing_users()

        cursor.executemany(add_query, add_params['values'])

        cursor.execute(*self.rollover_previous_data())

        update_queries = self.update_query()

        for query, param in update_queries:
            cursor.execute(query, param)

    @cached_property
    def get_dashboard_users(self):
        all_users = get_all_user_id_username_pairs_by_domain(self.domain, include_web_users=False,
                                                             include_mobile_users=True)
        dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')

        return {
            uname
            for id, uname in all_users
            if dashboard_uname_rx.match(uname)
        }

    def get_user_locations(self):
        user_locations = list()
        for username in self.get_dashboard_users:
            user = CommCareUser.get_by_username(username)
            loc = user.sql_location

            state_id, district_id, block_id, user_level = None, None, None, None

            if loc and loc.location_type.name == 'state':
                state_id = loc.location_id
                district_id = 'All'
                block_id = 'All'
                user_level = 1
            elif loc and loc.location_type.name == 'district':
                district_id = loc.location_id
                state_id = loc.get_ancestor_of_type('state').location_id
                block_id = 'All'
                user_level = 2
            elif loc and loc.location_type.name == 'block':
                block_id = loc.location_id
                district_id = loc.get_ancestor_of_type('district').location_id
                state_id = loc.get_ancestor_of_type('state').location_id
                user_level = 3
            user_locations.append((
                username,
                state_id,
                district_id,
                block_id,
                user_level
            ))

        return user_locations

    @property
    def tablename(self):
        return "{}_{}".format(self.aggregate_parent_table, self.date.strftime("%Y-%m-%d"))

    def drop_table_query(self):
        return 'DROP TABLE IF EXISTS "{}"'.format(self.tablename)

    def create_table_query(self):
        return """
        CREATE TABLE IF NOT EXISTS "{tablename}" (
            CHECK (date = DATE %(date)s),
            LIKE "{parent_tablename}" INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES
        ) INHERITS ("{parent_tablename}")
        """.format(
            parent_tablename=self.aggregate_parent_table,
            tablename=self.tablename,
        ), {
            "date": self.date.strftime("%Y-%m-%d"),
        }

    def get_last_agg_date(self):
        from custom.icds_reports.models.aggregate import DashboardUserActivityReport
        result = DashboardUserActivityReport.objects.filter(date__lt=self.date.strftime("%Y-%m-%d")).aggregate(Max('date'))
        if result:
            return result['date__max']
        return None

    def add_missing_users(self):
        return """
        
        INSERT INTO "{tablename}" (
            username, state_id, district_id,block_id,
            user_level,date
        )
        VALUES (%s,%s,%s,%s,%s, %s)
        """.format(
            tablename=self.tablename
        ), {
            'values': [tuple(list(loc) + [self.date]) for loc in self.get_user_locations()],
        }

    def rollover_previous_data(self):
        query_param = {'date': self.date,
                       'last_agg_date': self.last_agg_date}
        return """
        UPDATE "{tablename}" user_activity SET 
            location_launched = ut.location_launched, 
            last_activity = ut.last_activity
        FROM  (
        SELECT 
            username,
            location_launched,
            last_activity
            FROM "{parent_tablename}" WHERE date = %(last_agg_date)s
            )ut
        WHERE user_activity.username = ut.username 
        """.format(
            tablename=self.tablename,
            parent_tablename=self.aggregate_parent_table
        ), query_param

    def update_query(self):
        last_time_to_consider = self.date
        latest_month = (last_time_to_consider - timedelta(days=1)).replace(day=1)

        yield """
        UPDATE "{tablename}" user_activity 
            SET location_launched = CASE WHEN num_launched_blocks>0 THEN TRUE ELSE FALSE END
        FROM (
            SELECT
                block_id, district_id, state_id, num_launched_blocks,aggregation_level
            FROM agg_awc where month=%(latest_month)s and aggregation_level<=3
            ) ut
        WHERE (
            user_activity.user_level= ut.aggregation_level AND
            user_activity.state_id = ut.state_id AND
            user_activity.district_id = ut.district_id AND
            user_activity.block_id = ut.block_id AND
            user_activity.location_launched is not TRUE
        )
        """.format(
            tablename=self.tablename
        ), {
            'latest_month': latest_month
        }


        # This is query I prepare which could do what the last two queries are doing but the cost of this single query
        # coming out to be very high
        # yield """
        # UPDATE {tablename} user_activity
        # SET
        #     last_activity
        # from (
        # SELECT audit.username, max(audit.time_of_use) from {tablename} user_activity left join icds_audit_entry_record audit
        # on user_activity.username = audit.username
        # group by username where (user_activity.last_activity is not null time_of_use>user_activity.last_activity) or
        #                         ( user_activity.last_activity is null)
        # )ut
        # where user_activity.username = ut.username
        # """.format(tablename=self.tablename)

        yield """
        UPDATE "{tablename}" user_activity
        SET
            last_activity = ut.last_used
        FROM (
            SELECT 
                username,
                max(time_of_use)  as last_used
            FROM icds_audit_entry_record 
            WHERE username IN (
                SELECT username FROM "{tablename}" WHERE last_activity IS NULL
                ) AND time_of_use <= %(last_time_to_consider)s
            GROUP BY username
        ) ut
        WHERE user_activity.username = ut.username
        """.format(
            tablename=self.tablename
        ),{
            'last_time_to_consider': last_time_to_consider
        }

        yield """
        UPDATE "{tablename}" user_activity
        SET
            last_activity = ut.last_used
        FROM (
            SELECT 
                username,
                max(time_of_use)  as last_used
            FROM icds_audit_entry_record 
            WHERE username IN (
                SELECT username FROM "{tablename}" WHERE last_activity IS NOT NULL)  AND 
                time_of_use >= %(last_agg_date)s AND 
                time_of_use <= %(last_time_to_consider)s
            GROUP BY username
        ) ut
        WHERE user_activity.username = ut.username
        """.format(
            tablename=self.tablename
        ), {
            'last_agg_date': self.last_agg_date,
            'last_time_to_consider': last_time_to_consider
        }









