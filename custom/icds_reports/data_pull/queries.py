from datetime import date, timedelta

from django.db import connections
from django.utils.dateparse import parse_date
from django.utils.functional import cached_property

from dateutil.relativedelta import relativedelta


class BaseQuery:
    name = ""
    query_file_path = ""

    def run(self, db_alias):
        with open(self.result_file_name, "w") as output:
            db_conn = connections[db_alias]
            c = db_conn.cursor()
            query = self.sql_query
            query = query.replace('\n', ' ')
            c.copy_expert(
                "COPY ({query}) TO STDOUT DELIMITER ',' CSV HEADER;".format(query=query),
                output)
        return self.result_file_name

    @property
    def result_file_name(self):
        return "%s.csv" % self.name

    @cached_property
    def raw_query(self):
        filepath = 'custom/icds_reports/data_pull/sql_queries/%s.sql' % self.query_file_path
        with open(filepath) as _sql:
            sql = _sql.read()
        return sql

    def sql_query(self):
        raise NotImplemented


class MonthBasedQuery(BaseQuery):
    def __init__(self, month):
        self.month = month

    @property
    def result_file_name(self):
        return "%s-%s.csv" % (self.name, self.month)

    @cached_property
    def sql_query(self):
        return self.raw_query.format(month=self.month)


class LocationAndMonthBasedQuery(MonthBasedQuery):
    def __init__(self, location_id, month):
        super(LocationAndMonthBasedQuery, self).__init__(month)
        self.location_id = location_id

    @property
    def result_file_name(self):
        return "%s-%s-%s.csv" % (self.name, self.month, self.location_id)

    @cached_property
    def sql_query(self):
        return self.raw_query.format(location_id=self.location_id, month=self.month)


class PSEAbove3Years(LocationAndMonthBasedQuery):
    name = "PSE above 3 years"
    query_file_path = "pse_above_3_years"


class PSEAbove5Years(LocationAndMonthBasedQuery):
    name = "PSE above 5 years"
    query_file_path = "pse_above_5_years"


class LunchAbove3Years(LocationAndMonthBasedQuery):
    name = "Lunch above 3 years"
    query_file_path = "lunch_above_3_years"


class LunchAbove5Years(LocationAndMonthBasedQuery):
    name = "Lunch above 5 years"
    query_file_path = "lunch_above_5_years"


class THRPregnant(LocationAndMonthBasedQuery):
    name = "THR pregnant"
    query_file_path = "thr_pregnant"


class THRLactating(LocationAndMonthBasedQuery):
    name = "THR lactating"
    query_file_path = "thr_lactating"


class THRChildren(LocationAndMonthBasedQuery):
    name = "THR children"
    query_file_path = "thr_children"


class CBEConducted(LocationAndMonthBasedQuery):
    name = "CBE conducted"
    query_file_path = "cbe_conducted"

    @cached_property
    def sql_query(self):
        from_date = self.month
        till_date = str(parse_date(from_date) + relativedelta(months=1))
        return self.raw_query.format(location_id=self.location_id, from_date=from_date, till_date=till_date)
