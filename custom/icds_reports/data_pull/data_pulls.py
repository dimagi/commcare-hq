import calendar
import csv
import datetime
import io
from collections import defaultdict
from copy import copy

from django.utils.dateparse import parse_date

import openpyxl

from custom.icds.utils.location import find_test_state_locations
from custom.icds_reports.data_pull.exceptions import (
    DuplicateStateResult,
    UnboundDataPullException,
)
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
    VHSNDMonthlyCount,
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
        queries = []
        for query_class in self.queries:
            query_obj = query_class(self.month)
            if query_obj.setup_sql:
                queries.append(query_obj.setup_sql)
            queries.append(query_obj.sql_query)
        return queries

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
        return result


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
        test_state_names = self._get_test_state_names()
        state_name_column = 'state_name'
        for filename, filestream in data_files.items():
            filestream.seek(0)
            reader = csv.DictReader(filestream)
            for row in reader:
                state_name = row[state_name_column]
                if state_name in test_state_names:
                    continue
                for column_name, value in row.items():
                    if column_name != state_name_column:
                        result[state_name][column_name] = value
        return result

    @staticmethod
    def _get_test_state_names():
        return map(lambda loc: loc.name, find_test_state_locations())

    @staticmethod
    def _dump_consolidated_data(result):
        result_file = io.StringIO()
        headers = ['State']
        for state_name, col_values in result.items():
            for col_name in col_values:
                if col_name not in headers:
                    headers.append(col_name)
        writer = csv.DictWriter(result_file, headers)
        writer.writeheader()
        for state_name, col_values in result.items():
            row = copy(col_values)
            row['State'] = state_name
            writer.writerow(row)
        return result_file


class VHSNDMonthlyReport(MonthBasedDataPull):
    slug = "vhsnd_monthly_report"
    name = "VHSND monthly report"
    queries = [
        VHSNDMonthlyCount
    ]

    def post_run(self, data_files):
        state_results = self._consolidate_data(data_files)
        return self._dump_consolidated_data(state_results)

    def _consolidate_data(self, data_files):
        result = defaultdict(dict)
        for filename, filestream in data_files.items():
            filestream.seek(0)
            reader = csv.DictReader(filestream)
            for row in reader:
                state_name = row['state_name']
                vhsnd_date = parse_date(row['vhsnd_date_past_month']).strftime('%d/%m/%Y')
                data_key = (row['state_name'], row['district_name'], row['block_name'],
                            row['supervisor_name'], row['awc_name'])
                if data_key in result[state_name]:
                    result[state_name][data_key].append(vhsnd_date)
                else:
                    result[state_name][data_key] = [vhsnd_date]

        return self._format_consolidated_data(result)

    def _format_consolidated_data(self, result):
        # constructing headers
        headers, dates = self._get_headers_and_dates()
        # setting up workbooks for states
        state_results = self._setup_state_results_filestream(headers, result)
        # populating excel data
        for state_name, all_details in result.items():
            for details, vhsnd_dates in all_details.items():
                awc_row = list(copy(details))
                total_count = 0
                for a_date in dates:
                    if a_date in vhsnd_dates:
                        awc_row.append(1)
                        total_count += 1
                    else:
                        awc_row.append('')
                awc_row.append(total_count)
                state_results[state_name].append(awc_row)
        return {state_name: state_ws.parent for state_name, state_ws in state_results.items()}

    def _get_headers_and_dates(self):
        self.month_date = datetime.datetime.strptime(self.month, '%Y-%m-%d')
        num_days = calendar.monthrange(self.month_date.year, self.month_date.month)[1]
        days = [datetime.date(self.month_date.year, self.month_date.month, day) for day in range(1, num_days + 1)]

        dates = [day.strftime('%d/%m/%Y') for day in days]

        headers = ['State', 'District', 'Block', 'Sector', 'AWC']
        headers.extend(dates)
        headers.append('Grand Total')
        return headers, dates

    def _setup_state_results_filestream(self, headers, result):
        state_results = defaultdict(dict)
        for state_name in result.keys():
            # constructing and mapping writers to state names
            if state_name in state_results:
                raise DuplicateStateResult("%s is twice in results" % state_name)
            wb = openpyxl.Workbook()
            ws = wb.create_sheet(title=state_name, index=0)
            ws.append(headers)
            state_results[state_name] = ws
        return state_results

    def _dump_consolidated_data(self, result):
        output_files = defaultdict()
        for state_name, output_file in result.items():
            filename = "vhsnd_monthly_report_{}_{}_{}.xlsx".format(state_name, self.month_date.strftime('%b'),
                                                                   self.month_date.year)
            filestream = io.BytesIO()
            output_file.save(filestream)
            output_files[filename] = filestream
        return output_files
