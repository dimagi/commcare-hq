from __future__ import absolute_import
import csv
from datetime import datetime

from django.core.management.base import BaseCommand
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

DOMAIN = "enikshay"


class BaseDataDump(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(BaseDataDump, self).__init__(*args, **kwargs)
        self.log_progress = None
        self.result_file_name = None
        self.case_type = None
        self.input_file_name = None
        self.report = {}
        self.result_file_headers = []

    def add_arguments(self, parser):
        parser.add_argument('case_type')
        parser.add_argument('input_file_name')

    def setup_result_file_name(self):
        result_file_name = "data_dumps_{case_type}_{timestamp}.csv".format(
            case_type=self.case_type,
            timestamp=datetime.now().strftime("%Y-%m-%d--%H-%M-%S"),
        )
        return result_file_name

    def setup(self):
        with open(self.input_file_name, 'rU') as input_file:
            reader = csv.DictReader(input_file)
            for row in reader:
                self.report[row['Column Name']] = {
                    row['Case Reference']: row['Calculation']
                }
                self.result_file_headers.append(row['Column Name'])
        self.result_file_name = self.setup_result_file_name()

    def generate_dump(self):
        with open(self.result_file_name, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.result_file_headers)
            writer.writeheader()
            # iterate cases
            for case in self.get_cases(self.case_type):
                # store any references like last_episode or any data point
                # that might be needed repeatedly for the same case and is expensive call
                self.context = {}
                case_row = {}
                if not self.include_case_in_dump(case):
                    continue
                # iterate columns to be generated
                # details is a dict with key in [
                # "N/A" -> not to be populated so ignore it
                # self -> value would be a case property or some meta on the case itself
                # custom -> value would be some custom logic to be manually coded
                # specific case reference/association -> value would be case property on this associated case]
                for column_name, details in self.report.items():
                    for case_reference, calculation in details.items():
                        if case_reference == "N/A":
                            case_row[column_name] = "N/A"
                        elif case_reference == 'self':
                            if calculation == 'caseid':
                                case_row[column_name] = case.case_id
                            else:
                                case_row[column_name] = case.get_case_property(calculation)
                        elif case_reference == 'custom':
                            try:
                                case_row[column_name] = self.get_custom_value(column_name, case)
                            except Exception as e:
                                case_row[column_name] = str(e)
                        else:
                            try:
                                case_row[column_name] = self.get_case_reference_value(
                                    case_reference, case, calculation)
                            except Exception as e:
                                case_row[column_name] = str(e)

                writer.writerow(case_row)

    def get_cases(self, case_type):
        case_accessor = CaseAccessors(DOMAIN)
        return case_accessor.iter_cases(self.get_case_ids(case_type))

    def get_case_ids(self, case_type):
        raise NotImplementedError
