import io
from collections import defaultdict

from custom.icds_reports.data_pull.exceptions import UnboundDataPullException
from custom.icds_reports.data_pull.queries import (
    AWCSElectricityAndCBECount,
    AWCSFacilitiesCount,
    AWCSInfraFormsCount,
    AWCSLaunched,
    CBEConducted,
    ChildrenCount,
    ChildrenHeightAndWeightCount,
    ChildrenPSECount,
    ChildrenStuntedAndWastedCount,
    ChildrenTHRCount,
    DeliveriesAndRationCount,
    DirectQuery,
    HotCookedMealStats,
    LunchAbove3Years,
    LunchAbove5Years,
    PSEAbove3Years,
    PSEAbove5Years,
    PWAndLMTHRCount,
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

    def _get_data_files(self):
        raise NotImplementedError

    def run(self):
        data_files = self._get_data_files()
        return self.post_run(data_files)

    def post_run(self, data_files):
        """
        any tasks to be done post data pull
        :param data_files: file name mapped to string buffer for file content
        :return processed data_files
        """
        return data_files


class DirectDataPull(BaseDataPull):

    def __init__(self, db_alias, *args, **kwargs):
        super(DirectDataPull, self).__init__(db_alias, *args, **kwargs)
        self.query_file_path = kwargs.pop('query_file_path')
        self.name = self.query_file_path.rsplit('/')[-1].rsplit('.')[0]
        self.kwargs = kwargs

    def get_queries(self):
        query_obj = DirectQuery(self.name, self.query_file_path, **self.kwargs)
        return [query_obj.sql_query]

    def _get_data_files(self):
        query_obj = DirectQuery(self.name, self.query_file_path, **self.kwargs)
        return {
            query_obj.result_file_name: query_obj.run(self.db_alias)
        }


class MonthBasedDataPull(BaseDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(MonthBasedDataPull, self).__init__(db_alias, *args, **kwargs)
        self.month = kwargs.get('month')
        if not self.month:
            raise UnboundDataPullException("Month not defined")

    def get_queries(self):
        return [query_class(self.month).sql_query for query_class in self.queries]

    def _get_data_files(self):
        result = {}
        for query_class in self.queries:
            query_obj = query_class(self.month)
            result[query_obj.result_file_name] = query_obj.run(self.db_alias)
        return result


class LocationAndMonthBasedDataPull(MonthBasedDataPull):
    def __init__(self, db_alias, *args, **kwargs):
        super(LocationAndMonthBasedDataPull, self).__init__(db_alias, *args, **kwargs)
        self.location_id = kwargs.get('location_id')
        if not self.location_id:
            raise UnboundDataPullException("Location not defined")

    def get_queries(self):
        return [query_class(self.location_id, self.month).sql_query for query_class in self.queries]

    def _get_data_files(self):
        result = {}
        for query_class in self.queries:
            query_obj = query_class(self.location_id, self.month)
            result[query_obj.result_file_name] = query_obj.run(self.db_alias)
        return self.post_run(result)


class AndhraPradeshMonthly(LocationAndMonthBasedDataPull):
    slug = "andhra_pradesh_monthly"
    name = "Andhra Pradesh Monthly"
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


class MonthlyPerformance(MonthBasedDataPull):
    slug = "monthly_performance"
    name = "Monthly Performance"
    queries = [
        AWCSLaunched,
        AWCSInfraFormsCount,
        AWCSFacilitiesCount,
        AWCSElectricityAndCBECount,
        ChildrenTHRCount,
        ChildrenPSECount,
        PWAndLMTHRCount,
        ChildrenStuntedAndWastedCount,
        ChildrenHeightAndWeightCount,
        DeliveriesAndRationCount,
        HotCookedMealStats,
        ChildrenCount
    ]

    def post_run(self, data_files):
        result = self._consolidate_data(data_files)
        filestream = self._dump_consolidated_data(result)
        return {
            "Consolidated_monthly_report.csv": filestream
        }

    def _consolidate_data(self, data_files):
        result = defaultdict(dict)
        # ToDo: Consolidate data for all files into a single file
        return result

    @staticmethod
    def _dump_consolidated_data(result):
        result_file = io.StringIO()
        # ToDo: dump data in a csv file
        return result_file
