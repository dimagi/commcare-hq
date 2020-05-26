from io import StringIO

from django.db import connections
from django.utils.dateparse import parse_date
from django.utils.functional import cached_property

from dateutil.relativedelta import relativedelta


class BaseQuery:
    query_file_path = ""
    setup_sql_file_path = ""
    temp_table_name = ""

    def run(self, db_alias):
        # dropping any prev temp table from earlier queries
        if self.temp_table_name:
            self._remove_temp_table(db_alias)
        if self.setup_sql_file_path:
            self._setup(db_alias)
        string_buffer = StringIO()
        db_conn = connections[db_alias]
        cursor = db_conn.cursor()
        query = self.sql_query
        query = query.replace('\n', ' ')
        cursor.copy_expert(
            "COPY ({query}) TO STDOUT DELIMITER ',' CSV HEADER;".format(query=query),
            string_buffer)
        # dropping any temp table if created
        if self.temp_table_name:
            self._remove_temp_table(db_alias)
        return string_buffer

    def _setup(self, db_alias):
        db_conn = connections[db_alias]
        cursor = db_conn.cursor()
        sql = self.setup_sql.replace('\n', ' ')
        cursor.execute(sql)

    def _remove_temp_table(self, db_alias):
        db_conn = connections[db_alias]
        cursor = db_conn.cursor()
        sql = f"DROP TABLE IF EXISTS {self.temp_table_name}"
        cursor.execute(sql)

    @cached_property
    def setup_sql(self):
        if self.setup_sql_file_path:
            with open(self.setup_sql_file_path) as _sql:
                return _sql.read().format(month=self.month, temp_table=self.temp_table_name)

    @property
    def result_file_name(self):
        return "%s.csv" % self.name

    @cached_property
    def _raw_sql_query(self):
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
        return self._raw_sql_query.format(**self.kwargs)


class MonthBasedQuery(BaseQuery):
    def __init__(self, month):
        self.month = month

    @property
    def result_file_name(self):
        return "%s-%s.csv" % (self.name, self.month)

    @cached_property
    def sql_query(self):
        return self._raw_sql_query.format(month=self.month)


class LocationAndMonthBasedQuery(MonthBasedQuery):
    def __init__(self, location_id, month):
        super(LocationAndMonthBasedQuery, self).__init__(month)
        self.location_id = location_id

    @property
    def result_file_name(self):
        return "%s-%s-%s.csv" % (self.name, self.month, self.location_id)

    @cached_property
    def sql_query(self):
        return self._raw_sql_query.format(location_id=self.location_id, month=self.month)


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
        return self._raw_sql_query.format(location_id=self.location_id,
                                          from_date=from_date, till_date=till_date)


class AWCSLaunched(MonthBasedQuery):
    name = "AWCs launched"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/awcs_launched.sql"


class AWCSInfraFormsCount(MonthBasedQuery):
    name = "AWCs Infra Forms Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/awcs_infra_forms_count.sql"


class AWCSFacilitiesCount(MonthBasedQuery):
    name = "AWCs Facilities Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/awcs_facilities_count.sql"


class AWCSElectricityAndCBECount(MonthBasedQuery):
    name = "AWCs Electricity And CBE Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/awcs_electricity_and_cbe_count.sql"


class ChildrenTHRCount(MonthBasedQuery):
    name = "Children THR Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/children_thr_count.sql"
    setup_sql_file_path = "custom/icds_reports/data_pull/sql_queries/create_tmp_thr_table.sql"
    temp_table_name = "temp_thr_data_pull"


class ChildrenPSECount(MonthBasedQuery):
    name = "Children PSE Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/children_pse_count.sql"
    setup_sql_file_path = "custom/icds_reports/data_pull/sql_queries/create_tmp_pse_table.sql"
    temp_table_name = "temp_pse_data_pull"


class PWAndLMTHRCount(MonthBasedQuery):
    name = "Pregnant Women and Lactating Mother THR Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/pw_and_lm_thr_count.sql"
    setup_sql_file_path = "custom/icds_reports/data_pull/sql_queries/create_dummy_thr_table.sql"
    temp_table_name = "dummy_thr_table"


class ChildrenStuntedAndWastedCount(MonthBasedQuery):
    name = "Children Stunted And Wasted Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/children_stunted_and_wasted_count.sql"


class ChildrenHeightAndWeightCount(MonthBasedQuery):
    name = "Children Height And Weight Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/children_height_and_weight_count.sql"


class DeliveriesAndRationCount(MonthBasedQuery):
    name = "Deliveries And Ration Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/deliveries_and_ration_count.sql"


class HotCookedMealStats(MonthBasedQuery):
    name = "Hot Cooked Meal Stats"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/hot_cooked_meal_stats.sql"


class ChildrenCount(MonthBasedQuery):
    name = "Children Count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/children_count.sql"


class VHSNDMonthlyCount(MonthBasedQuery):
    name = "VNSND monthly count"
    query_file_path = "custom/icds_reports/data_pull/sql_queries/vhsnd_monthly_report.sql"
