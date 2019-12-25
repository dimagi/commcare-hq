from custom.icds_reports.data_pull.exceptions import UnboundDataPull


class BaseDataPull:
    slug = ""
    queries = []

    def __init__(self, db_alias, *args, **kwargs):
        self.db_alias = db_alias

    def get_queries(self):
        return [query_class().sql_query for query_class in self.queries]

    def run(self):
        return [query_class().run(self.db_alias) for query_class in self.queries]


class MonthlyDataPull(BaseDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(MonthlyDataPull, self).__init__(db_alias, *args, **kwargs)
        self.month = kwargs.get('month')

    def get_queries(self):
        return [query_class(self.month).sql_query for query_class in self.queries]

    def run(self):
        if not self.month:
            raise UnboundDataPull("Month not defined")
        return [query_class(self.month).run(self.db_alias) for query_class in self.queries]


class LocationAndMonthBasedDataPull(MonthlyDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(LocationAndMonthBasedDataPull, self).__init__(db_alias, *args, **kwargs)
        self.location_id = kwargs.get('location_id')

    def get_queries(self):
        return [query_class(self.location_id, self.month).sql_query for query_class in self.queries]

    def run(self):
        if not self.location_id:
            raise UnboundDataPull("Location not defined")
        return [query_class(self.location_id, self.month).run(self.db_alias) for query_class in self.queries]
