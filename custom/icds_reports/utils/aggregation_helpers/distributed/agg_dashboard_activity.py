from datetime import timedelta, date
from django.db.models import Max

from custom.icds_reports.utils.aggregation_helpers.distributed.base import BaseICDSAggregationDistributedHelper
from custom.icds_reports.const import AGG_DASHBOARD_ACTIVITY
from django.utils.functional import cached_property
from django.contrib.auth.models import User
from corehq.apps.users.dbaccessors.all_commcare_users import get_user_docs_by_username
from dimagi.utils.chunked import chunked


class DashboardActivityReportAggregate(BaseICDSAggregationDistributedHelper):
    aggregate_parent_table = AGG_DASHBOARD_ACTIVITY

    def __init__(self, date):
        self.date = date
        self.last_agg_date = self.get_last_agg_date()

    def aggregate(self, cursor):
        drop_query = self.drop_table_query()
        create_table_query, create_table_param = self.create_table_query()
        add_query, add_params = self.add_latest_users_list()

        rollover_query, rollover_param = self.rollover_previous_data()
        update_queries = self.update_queries()

        cursor.execute(drop_query)
        cursor.execute(create_table_query, create_table_param)
        cursor.cursor.execute(add_query, add_params)
        cursor.execute(rollover_query, rollover_param)

        for query, param in update_queries:
            cursor.execute(query, param)

    @cached_property
    def dashboard_users(self):
        usernames = User.objects.filter(username__regex=r'^\d*\.[a-zA-Z]*@.*').values_list('username',
                                                                                           flat=True)
        user_docs = list()
        for user_list in chunked(usernames, 200):
            user_docs.extend(get_user_docs_by_username(user_list))

        return user_docs

    @cached_property
    def transformed_locations(self):
        """
        :return: Returns a dict containing location_id as key and its info(loc_level,parents) as value
                eg: {
                        block_loc_id1: {
                            'loc_level':3,
                            'parents':{
                                'district_id': 'district_loc_id1',
                                'state_id': 'state_loc_id1'
                            }
                        }
                    }
        """
        from custom.icds_reports.models.aggregate import AwcLocation
        locations = (AwcLocation.objects.filter(aggregation_level=3).
                     exclude(state_is_test=1).
                     values('state_id', 'district_id', 'block_id'))

        transformed_locations = dict()

        for loc in locations:
            state_id = loc['state_id']
            district_id = loc['district_id']
            block_id = loc['block_id']

            if state_id not in transformed_locations:
                transformed_locations[state_id] = {'loc_level': 1}

            if district_id not in transformed_locations:
                transformed_locations[district_id] = {
                    'loc_level': 2,
                    'parents': {
                        'state_id': state_id
                    }
                }

            if block_id not in transformed_locations:
                transformed_locations[block_id] = {
                    'loc_level': 3,
                    'parents': {
                        'district_id': district_id,
                        'state_id': state_id
                    }
                }
        return transformed_locations

    def get_user_locations(self):
        user_locations = list()
        for user in self.dashboard_users:
            state_id, district_id, block_id, user_level = None, None, None, None
            usr_assigned_actual_loc = user['location_id'] and user['location_id'] in self.transformed_locations

            if usr_assigned_actual_loc and user.get('is_active'):
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

        #because we dont expect the report to fail for 7 consecutive days
        seven_days_back = self.date - timedelta(days=7)

        result = (DashboardUserActivityReport.objects.
                  filter(date__lt=self.date.strftime("%Y-%m-%d"), date__gt=seven_days_back).
                  aggregate(Max('date')))

        last_agg_date = result.get('date__max')
        return last_agg_date or date(1970, 1, 1)  # return the oldest date in default case

    def add_latest_users_list(self):

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

        yield """
        UPDATE  "{tablename}" user_activity
        SET
            last_activity = ut.last_activity
        FROM (
        SELECT audit.username, max(audit.time_of_use)  AS last_activity FROM "{tablename}" user_activity
            left join icds_audit_entry_record audit ON user_activity.username = audit.username
        where audit.time_of_use>=%(last_agg_date)s AND
              audit.time_of_use<%(last_time_to_consider)s
        GROUP BY audit.username
        )ut
        WHERE user_activity.username = ut.username and ut.last_activity is not null;
        """.format(
            tablename=self.tablename
        ), {
            'last_agg_date': self.last_agg_date,
            'last_time_to_consider': last_time_to_consider
        }
