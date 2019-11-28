from datetime import timedelta
from django.db.models import Max

import re

from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from custom.icds_reports.const import  AGG_DASHBOARD_ACTIVITY
from django.utils.functional import cached_property
from corehq.apps.es import UserES


class DashboardActivityReportAggregate(BaseICDSAggregationDistributedHelper):
    aggregate_parent_table = AGG_DASHBOARD_ACTIVITY

    def __init__(self, date):
        self.date = date
        self.last_agg_date = self.get_last_agg_date()

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        create_table_query, create_table_param = self.create_table_query()
        add_query, add_params = self.add_missing_users()
        rollover_query, rollover_param = self.rollover_previous_data()
        update_queries = self.update_queries()

        cursor.execute(drop_query)
        cursor.execute(create_table_query, create_table_param)
        cursor.cursor.execute(add_query, add_params)
        cursor.execute(rollover_query, rollover_param)

        for query, param in update_queries:
            cursor.execute(query, param)

    @cached_property
    def get_dashboard_users(self):
        user_query = UserES().mobile_users().domain(self.domain).location(
            list(self.transformed_locations.keys())).fields(['username', 'location_id'])

        all_users = [u for u in user_query.run().hits]
        dashboard_uname_rx = re.compile(r'^\d*\.[a-zA-Z]*@.*')

        return [
            user
            for user in all_users
            if dashboard_uname_rx.match(user['username'])
        ]

    @cached_property
    def transformed_locations(self):
        """
        :return: Returns a dict containing location_id as key and its info(loc_level,parents) as value
                eg: {block_loc_id1: {'loc_level':3, parents:{
                                                    'district_id': district_loc_id1,
                                                    'state_id': state_loc_id1
                                                }
                                    }
                    }
        """
        from custom.icds_reports.models.aggregate import AwcLocation
        locations = AwcLocation.objects.filter(aggregation_level=3).values('state_id', 'district_id', 'block_id')

        transformed_locations = dict()

        for loc in locations:
            state_id = loc['state_id']
            district_id = loc['district_id']
            block_id = loc['block_id']

            if state_id not in transformed_locations:
                transformed_locations[state_id] = {'loc_level': 1}

            if district_id not in transformed_locations:
                transformed_locations[district_id] = {'loc_level': 2,
                                                      'parents': {
                                                          'state_id': state_id
                                                      }
                                                      }
            if block_id not in transformed_locations:
                transformed_locations[block_id] = {'loc_level': 3,
                                                   'parents': {
                                                       'district_id': district_id,
                                                       'state_id': state_id
                                                   }
                                                   }
        return transformed_locations

    def get_user_locations(self):
        user_locations = list()
        for user in self.get_dashboard_users:

            state_id, district_id, block_id, user_level = None, None, None, None

            if user['location_id']:
                user_level = self.transformed_locations.get(user['location_id'])['loc_level']

                if user_level == 1:
                    state_id = user['location_id']
                    district_id = 'All'
                    block_id = 'All'
                elif user_level == 2:
                    state_id = self.transformed_locations.get(user['location_id'])['parents']['state_id']
                    district_id = user['location_id']
                    block_id = 'All'
                elif user_level == 3:
                    state_id = self.transformed_locations.get(user['location_id'])['parents']['state_id']
                    district_id = self.transformed_locations.get(user['location_id'])['parents']['district_id']
                    block_id = user['location_id']

            user_locations.append((
                user['username'],
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
        result = DashboardUserActivityReport.objects.\
            filter(date__lt=self.date.strftime("%Y-%m-%d")).\
            aggregate(Max('date'))
        if result:
            return result['date__max']
        return None

    def add_missing_users(self):

        parameters = {'value{}'.format(index): tuple(list(loc) + [self.date])
                      for index, loc in enumerate(self.get_user_locations())
                      }
        param_keys = ['%({})s'.format(param) for param in parameters.keys()]

        return """
        INSERT INTO "{tablename}" (
            username, state_id, district_id,block_id,
            user_level,date
        )
        VALUES {param_keys}
        """.format(
            tablename=self.tablename,
            param_keys=','.join(param_keys)
        ), parameters

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

    def update_queries(self):
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

        # This is query I prepare which could do what the last two queries are doing but
        # the cost of this single query coming out to be very high
        # yield """
        # UPDATE {tablename} user_activity
        # SET
        #     last_activity
        # from (
        # SELECT audit.username, max(audit.time_of_use) from {tablename} user_activity left join
        # icds_audit_entry_record audit
        # on user_activity.username = audit.username
        # group by username where (user_activity.last_activity is not null AND
        #                          time_of_use>user_activity.last_activity
        #                           ) or
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
        ), {
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
