import csv
import json
from datetime import date

from django.core.management.base import BaseCommand

from custom.icds_reports.reports.poshan_progress_dashboard_data import get_poshan_progress_dashboard_data
from custom.icds_reports.sqldata.exports.poshan_progress_report import PoshanProgressReport


class Command(BaseCommand):

    def handle(self, *args, **options):
        location = ''
        data = PoshanProgressReport(
            config={
                'domain': 'icds-cas',
                'month': date(2020, 5, 1),
                'report_layout': 'comprehensive',
                'data_period': 'quarter',
                'quarter': 1,
                'year': 2020
            },
            loc_level=1
        ).get_excel_data(location)
        fout = open(f'build_progress_report.csv', 'w')
        writer = csv.writer(fout)
        writer.writerows(data[0][1])


        data = get_poshan_progress_dashboard_data('icds-cas', 2020, None, 1, 'quarter', 'comparative',
                                                  {'aggregation_level': 1}, False
                                                  )
        comparitive = open(f'ppd_comparitive.json', "w")
        json.dump(data, comparitive, indent=4)
        comparitive.close()
        data = get_poshan_progress_dashboard_data('icds-cas', 2020, None, 1, 'quarter', 'aggregated',
                                                  {'aggregation_level': 1}, False
                                                  )
        aggregated = open(f'ppd_aggregated.json', "w")
        json.dump(data, aggregated, indent=4)
        aggregated.close()

