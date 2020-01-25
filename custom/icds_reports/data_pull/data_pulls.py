from custom.icds_reports.data_pull.exceptions import UnboundDataPullException
from custom.icds_reports.data_pull.queries import (
    CBEConducted,
    DirectQuery,
    LunchAbove3Years,
    LunchAbove5Years,
    PSEAbove3Years,
    PSEAbove5Years,
    THRChildren,
    THRLactating,
    THRPregnant,
)


class BaseDataPull:
    slug = ""
    name = ""
    queries = None  # list of query classes

    def __init__(self, db_alias, *args, **kwargs):
        self.db_alias = db_alias

    def get_queries(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError


class DirectDataPull(BaseDataPull):

    def __init__(self, db_alias, *args, **kwargs):
        super(DirectDataPull, self).__init__(db_alias, *args, **kwargs)
        self.query_file_path = kwargs.pop('query_file_path')
        self.name = self.query_file_path.rsplit('/')[-1].rsplit('.')[0]
        self.kwargs = kwargs

    def get_queries(self):
        query_obj = DirectQuery(self.name, self.query_file_path, **self.kwargs)
        return [query_obj.sql_query]

    def run(self):
        query_obj = DirectQuery(self.name, self.query_file_path, **self.kwargs)
        return {
            query_obj.result_file_name: query_obj.run(self.db_alias)
        }


class MonthlyDataPull(BaseDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(MonthlyDataPull, self).__init__(db_alias, *args, **kwargs)
        self.month = kwargs.get('month')
        if not self.month:
            raise UnboundDataPullException("Month not defined")

    def get_queries(self):
        return [query_class(self.month).sql_query for query_class in self.queries]

    def run(self):
        result = {}
        for query_class in self.queries:
            query_obj = query_class(self.month)
            result[query_obj.result_file_name] = query_obj.run(self.db_alias)
        return result


class LocationAndMonthBasedDataPull(MonthlyDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(LocationAndMonthBasedDataPull, self).__init__(db_alias, *args, **kwargs)
        self.location_id = kwargs.get('location_id')
        if not self.location_id:
            raise UnboundDataPullException("Location not defined")

    def get_queries(self):
        return [query_class(self.location_id, self.month).sql_query for query_class in self.queries]

    def run(self):
        result = {}
        for query_class in self.queries:
            query_obj = query_class(self.location_id, self.month)
            result[query_obj.result_file_name] = query_obj.run(self.db_alias)
        return result


class MonthlyPerformance(LocationAndMonthBasedDataPull):
    slug = "monthly_performance"
    name = "Monthly Performance"
    queries = [
        CBEConducted,
        LunchAbove3Years,
        LunchAbove5Years,
        PSEAbove3Years,
        PSEAbove5Years,
        THRChildren,
        THRLactating,
        THRPregnant,
    ]
