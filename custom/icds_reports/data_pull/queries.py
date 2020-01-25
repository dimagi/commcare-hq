from io import StringIO

from django.db import connections
from django.utils.dateparse import parse_date
from django.utils.functional import cached_property

from dateutil.relativedelta import relativedelta


class BaseQuery:
    query_file_path = ""

    def run(self, db_alias):
        string_buffer = StringIO()
        db_conn = connections[db_alias]
        cursor = db_conn.cursor()
        query = self.sql_query
        query = query.replace('\n', ' ')
        cursor.copy_expert(
            "COPY ({query}) TO STDOUT DELIMITER ',' CSV HEADER;".format(query=query),
            string_buffer)
        return string_buffer

    @property
    def result_file_name(self):
        return "%s.csv" % self.name

    @cached_property
    def _raw_query(self):
        with open(self.query_file_path) as _sql:
            return _sql.read()

    @cached_property
    def sql_query(self):
        raise NotImplementedError


class DirectQuery(BaseQuery):
    def __init__(self, name, query_file_path, **kwargs):
        self.name = name
        self.query_file_path = query_file_path
        self.kwargs = kwargs

    @cached_property
    def sql_query(self):
        return self._raw_query.format(**self.kwargs)


class MonthBasedQuery(BaseQuery):
    def __init__(self, month):
        self.month = month

    @property
    def result_file_name(self):
        return "%s-%s.csv" % (self.name, self.month)

    @cached_property
    def sql_query(self):
        return self._raw_query.format(month=self.month)


class LocationAndMonthBasedQuery(MonthBasedQuery):
    def __init__(self, location_id, month):
        super(LocationAndMonthBasedQuery, self).__init__(month)
        self.location_id = location_id

    @property
    def result_file_name(self):
        return "%s-%s-%s.csv" % (self.name, self.month, self.location_id)

    @cached_property
    def sql_query(self):
        return self._raw_query.format(location_id=self.location_id, month=self.month)


class PSEAbove3Years(LocationAndMonthBasedQuery):
    name = "PSE above 3 years"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/pse_above_3_years.sql"


class PSEAbove5Years(LocationAndMonthBasedQuery):
    name = "PSE above 5 years"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/pse_above_5_years.sql"


class LunchAbove3Years(LocationAndMonthBasedQuery):
    name = "Lunch above 3 years"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/lunch_above_3_years.sql"


class LunchAbove5Years(LocationAndMonthBasedQuery):
    name = "Lunch above 5 years"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/lunch_above_5_years.sql"


class THRPregnant(LocationAndMonthBasedQuery):
    name = "THR pregnant"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/thr_pregnant.sql"


class THRLactating(LocationAndMonthBasedQuery):
    name = "THR lactating"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/thr_lactating.sql"


class THRChildren(LocationAndMonthBasedQuery):
    name = "THR children"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/thr_children.sql"


class CBEConducted(LocationAndMonthBasedQuery):
    name = "CBE conducted"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/cbe_conducted.sql"

    @cached_property
    def sql_query(self):
        from_date = self.month
        till_date = str(parse_date(from_date) + relativedelta(months=1))
        return self._raw_query.format(location_id=self.location_id,
                                      from_date=from_date, till_date=till_date)
