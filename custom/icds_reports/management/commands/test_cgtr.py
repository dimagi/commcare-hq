from datetime import date
from custom.icds_reports.sqldata.exports.growth_tracker_report import GrowthTrackerExport
from cProfile import Profile
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('district_id')

    def _handle(self, district_id):
        t = GrowthTrackerExport(
            config={
                'domain': 'icds-cas',
                'month': date(2017, 5, 1),
                'district_id': district_id
            },
            loc_level=2).get_excel_data('d1')
        return t

    def handle(self, district_id, *args, **options):
        profiler = Profile()
        profiler.runcall(self._handle, district_id)
        profiler.print_stats()
