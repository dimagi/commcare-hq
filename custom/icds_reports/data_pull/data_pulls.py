from custom.icds_reports.data_pull.exceptions import UnboundDataPullException
from custom.icds_reports.data_pull.queries import (
    CBEConducted,
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
        if not self.queries:
            return []
        return [query_class().sql_query for query_class in self.queries]

    def run(self):
        if not self.queries:
            return []
        return [query_class().run(self.db_alias) for query_class in self.queries]


class MonthlyDataPull(BaseDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(MonthlyDataPull, self).__init__(db_alias, *args, **kwargs)
        self.month = kwargs.get('month')

    def get_queries(self):
        return [query_class(self.month).sql_query for query_class in self.queries]

    def run(self):
        if not self.month:
            raise UnboundDataPullException("Month not defined")
        return [query_class(self.month).run(self.db_alias) for query_class in self.queries]


class LocationAndMonthBasedDataPull(MonthlyDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(LocationAndMonthBasedDataPull, self).__init__(db_alias, *args, **kwargs)
        self.location_id = kwargs.get('location_id')

    def get_queries(self):
        return [query_class(self.location_id, self.month).sql_query for query_class in self.queries]

    def run(self):
        if not self.location_id:
            raise UnboundDataPullException("Location not defined")
        return [query_class(self.location_id, self.month).run(self.db_alias) for query_class in self.queries]


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
