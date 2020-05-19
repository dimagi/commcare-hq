import csv
from datetime import date

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand

from custom.icds_reports.models import AwcLocation, AggAwc


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        self.run_task()

    def run_task(self):
        start_date = date(2018, 10, 1)
        end_date = date(2020, 4, 1)
        columns = ['awc', 'awc_site_code', 'supervisor', 'district', 'block']
        date_itr = start_date
        count = 0
        while date_itr <= end_date:
            columns.append(date_itr.strftime("%Y-%m-%d"))
            date_itr = date_itr + relativedelta(months=1)
            count = count + 1
        awc_data = AwcLocation.objects.filter(aggregation_level=5,
                                              state_id='f98e91aa003accb7b849a0f18ebd7039').values('doc_id',
                                                                                                  'awc_name',
                                                                                                  'awc_site_code',
                                                                                                  'supervisor_name',
                                                                                                  'block_name',
                                                                                                  'district_name')
        data_format = {}
        for awc in awc_data:
            data_format.update({awc['doc_id']: [awc['awc_name'], awc['awc_site_code'], awc['supervisor_name'],
                                                awc['district_name'], awc['block_name']] + ['N' for _ in
                                                                                            range(0, count)]})
        date_itr = start_date
        while date_itr <= end_date:
            month = date_itr.strftime("%Y-%m-%d")
            visit_data = AggAwc.objects.filter(aggregation_level=5, state_id='f98e91aa003accb7b849a0f18ebd7039',
                                               month=month).values('awc_id',
                                                                   'expected_visits',
                                                                   'valid_visits',
                                                                   'num_launched_awcs')

            for row in visit_data:
                if row['num_launched_awcs'] != 1:
                    data_format[row['awc_id']][columns.index(month)] = 'Not Launched'
                elif row['expected_visits'] > 0:
                    if (float(row['valid_visits']) / float(row['expected_visits'])) >= 0.6:
                        data_format[row['awc_id']][columns.index(month)] = 'Y'
            date_itr = date_itr + relativedelta(months=1)
        final_rows = [[columns]]
        for k in data_format:
            final_rows.append(data_format[k])
        fout = open(f'/home/cchq/AP_home_visit.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(final_rows)
