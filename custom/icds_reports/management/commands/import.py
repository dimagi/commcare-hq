
from django.core.management.base import BaseCommand

from corehq.apps.locations.models import LocationType, SQLLocation
from custom.icds_reports.models import AwcLocation


DOMAIN = 'icds-test'


class Command(BaseCommand):
    def handle(self, *args, **options):
        locations = AwcLocation.objects.using('icds').all()

        name_properties = [
            'awc_name',
            'supervisor_name',
            'block_name',
            'district_name',
            'state_name'
        ]

        previous = None

        SQLLocation.objects.filter(domain=DOMAIN).delete()
        LocationType.objects.filter(domain=DOMAIN).delete()

        for p in name_properties[::-1]:
            previous = LocationType.objects.get_or_create(name=p[:-5], domain=DOMAIN, parent_type=previous)[0]

        location_types = {
            location_type.name: location_type
            for location_type in LocationType.objects.filter(domain=DOMAIN)
        }

        name_properties = name_properties[::-1]
        currently_added = set()
        locations_cache = {}
        for idx, prop in enumerate(name_properties):
            for location in locations:
                name = getattr(location, prop)
                if name not in (None, 'All'):
                    if prop[:-5] == 'awc':
                        location_id = location.doc_id
                    else:
                        location_id = getattr(location, '{}_id'.format(prop[:-5]))

                    if location_id in currently_added:
                        continue
                    else:
                        currently_added.add(location_id)

                    location_type = location_types.get(prop[:-5])
                    if idx == 0:
                        parent = None
                    else:
                        parent_id_key = '{}_id'.format(name_properties[idx - 1][:-5])
                        parent = locations_cache.get(getattr(location, parent_id_key)).pk or SQLLocation.objects.get(
                            location_id=getattr(location, parent_id_key)
                        ).pk

                    locations_cache[location_id] = SQLLocation.objects.create(
                        location_id=location_id,
                        domain=DOMAIN,
                        location_type=location_type,
                        name=name,
                        parent_id=parent
                    )