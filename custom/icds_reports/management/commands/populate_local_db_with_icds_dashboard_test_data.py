
from django.core.management.base import BaseCommand, CommandError
from psycopg2._psycopg import IntegrityError

import settings
from corehq.apps.locations.models import SQLLocation
from custom.icds_reports.models import AwcLocation
from custom.icds_reports.models.aggregate import AwcLocationLocal, get_cursor
from custom.icds_reports.tests import agg_tests


class Command(BaseCommand):
    help = "Populates your local database with test data for the dashboard."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This command is only allowed in DEBUG mode to prevent accidental data deletion")

        proceed_str = input(
            '=================================================\n'
            'This command deletes a lot of things, including: \n'
            ' - ALL local location information\n'
            ' - ALL local ICDS UCR data\n\n'
            'Are you sure you want to proceed? (y/N)\n')
        if proceed_str.lower().strip() == 'y':
            try:
                agg_tests.setUpModule()
            except IntegrityError:
                print(
                    '=================================================\n'
                    'It looks like your existing data conflicted with setup. \n'
                    'You may need to manually delete some data from tables.\n'
                    '=================================================\n'
                )
                raise
            _rename_locations()
        else:
            print('operation canceled')


def _rename_locations():
    # we need to use real location names because the map depends on names as keys
    new_name_map = (
        ('state_name', 'st1', 'Bihar'),
        ('district_name', 'd1', 'Patna'),
        ('block_name', 'b1', 'Bihta'),

    )
    for location_name_column, old_name, new_name in new_name_map:
        _rename_location(location_name_column, old_name, new_name)


def _rename_location(location_name_column, old_name, new_name):
    try:
        location = SQLLocation.objects.get(name=old_name)
        location.name = new_name
        location.save()
    except SQLLocation.DoesNotExist:
        print(f'location {old_name} not found!')

    AwcLocation.objects.filter(**{location_name_column: old_name}).update(**{location_name_column: new_name})
    with get_cursor(AwcLocationLocal) as cursor:
        cursor.execute(
            f"UPDATE awc_location_local SET {location_name_column}='{new_name}' where {location_name_column} = '{old_name}'"
        )
