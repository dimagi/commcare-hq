from django.core.management.base import BaseCommand
from corehq.apps.locations.models import SQLLocation,LocationType
from custom.icds_reports.reports.fact_sheets import FactSheetsReport
import datetime
import cProfile


def get_time_taken(fconfig):
    start = datetime.datetime.now()
    data = FactSheetsReport(
        config=fconfig, loc_level='district', show_test=False, beta=False
    ).get_data()
    return datetime.datetime.now() - start


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('state_id')
        parser.add_argument('district_id')
        parser.add_argument('district_name')
        parser.add_argument('--profile', action='store_true')

    def handle(self, state_id, district_id, district_name, **options):
        loc_type = LocationType.objects.get(name='district', domain='icds-cas')
        fconfig = {
            'aggregation_level': 2,
            'month': datetime.date(2020, 5, 1),
            'previous_month': datetime.date(2020, 6, 1),
            'two_before': datetime.date(2020,3, 1),
            'category': 'all',
            'domain': 'icds-cas',
            'state_id': state_id,
            'district_id': district_id,
            'sql_location': SQLLocation(domain='icds-cas', name=district_name, location_type=loc_type)
        }

        if options.get('profile'):
            cProfile('get_time_taken(fconfig)')
        else:
            for i in range(0, 10):
                print(get_time_taken(fconfig))
