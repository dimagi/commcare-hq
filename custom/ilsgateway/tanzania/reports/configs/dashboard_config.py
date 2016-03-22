from datetime import timedelta

from django.db import connection

from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import DeliveryGroups
from dimagi.utils.dates import get_business_day_of_month
from dimagi.utils.decorators.memoized import memoized


class DashboardConfig(object):
    def __init__(self, domain, location_id, start_date, end_date):
        self.domain = domain
        self.location_id = location_id
        self.start_date = start_date
        self.end_date = end_date

    @property
    @memoized
    def sql_location(self):
        return SQLLocation.objects.get(domain=self.domain, location_id=self.location_id)

    @property
    @memoized
    def descendants(self):
        return list(self.sql_location.get_descendants().filter(location_type__administrative=False)
                    .exclude(is_archived=True))

    @property
    @memoized
    def case_ids(self):
        return tuple([sql_location.supply_point_id for sql_location in self.descendants])

    @memoized
    def get_location_ids(self, group):
        if not group:
            return tuple([sql_location.supply_point_id for sql_location in self.descendants])
        else:
            return tuple(
                [
                    sql_location.location_id
                    for sql_location in self.descendants
                    if sql_location.metadata.get('group') == group
                ]
            )

    @property
    @memoized
    def soh_data_total(self):
        if not self.case_ids:
            return {}
        previous_month_date = (self.start_date.replace(day=1) - timedelta(days=1))
        pm_last_business_day = get_business_day_of_month(previous_month_date.year, previous_month_date.month, -1)
        on_time_date = get_business_day_of_month(self.start_date.year, self.start_date.month, 6)
        cm_last_business_day = get_business_day_of_month(self.start_date.year, self.start_date.month, -1)
        query = """
        SELECT status, COUNT(case_id) FROM
            (
                SELECT DISTINCT ON (case_id) case_id,
                CASE WHEN sr.date::date < %s THEN 'on_time' ELSE 'late' END as status
                FROM stock_stocktransaction st JOIN stock_stockreport sr ON sr.id = st.report_id
                WHERE sr.domain = %s AND sr.date BETWEEN %s AND %s AND case_id IN %s
                AND st.type IN ('stockonhand', 'stockout')
                ORDER BY case_id, sr.date
            )x
        GROUP BY status;
        """
        with connection.cursor() as cursor:
            cursor.execute(query, [
                on_time_date, self.domain, pm_last_business_day,
                cm_last_business_day - timedelta(microseconds=1), self.case_ids
            ])
            rows = cursor.fetchall()
        return dict(rows)

    @property
    @memoized
    def rr_data_total(self):
        current_submitting_group = DeliveryGroups(self.start_date.month).current_submitting_group()
        location_ids = self.get_location_ids(current_submitting_group)
        if not location_ids:
            return {}
        on_time_date = get_business_day_of_month(self.start_date.year, self.start_date.month, 13)
        query = """
            SELECT status, status_value, COUNT(location_id) FROM
                (
                    SELECT DISTINCT ON (location_id) location_id, status_value,
                    CASE WHEN status_date::date < %s THEN 'on_time' ELSE 'late' END as status
                    FROM ilsgateway_supplypointstatus
                    WHERE status_date BETWEEN %s AND %s AND status_type='rr_fac'
                    AND status_value != 'reminder_sent' AND location_id IN %s
                    ORDER BY location_id, status_date DESC
                )x
            GROUP BY status, status_value;

        """
        with connection.cursor() as cursor:
            cursor.execute(query, [on_time_date, self.start_date, self.end_date, location_ids])
            rows = cursor.fetchall()
        rows = [((status, status_value), count) for status, status_value, count in rows]
        rows.append(('total', len(location_ids)))
        return dict(rows)

    @property
    @memoized
    def delivery_data_total(self):
        current_delivering_group = DeliveryGroups(self.start_date.month).current_delivering_group()
        location_ids = self.get_location_ids(current_delivering_group)
        if not location_ids:
            return {}
        query = """
            SELECT status_value, COUNT(location_id) FROM
                (
                    SELECT DISTINCT ON (location_id) location_id, status_value
                    FROM ilsgateway_supplypointstatus
                    WHERE status_date BETWEEN %s AND %s AND status_type = 'del_fac'
                    AND status_value != 'reminder_sent' AND location_id IN %s
                    ORDER BY location_id, status_date DESC
                )x
            GROUP BY status_value;

        """
        with connection.cursor() as cursor:
            cursor.execute(query, [self.start_date, self.end_date, location_ids])
            rows = cursor.fetchall()
        rows.append(('total', len(location_ids)))
        return dict(rows)
