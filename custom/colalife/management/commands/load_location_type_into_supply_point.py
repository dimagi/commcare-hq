from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Store location type with supply point.'

    def handle(self, *args, **options):
        for location_type in ["wholesaler", "retailer"]:
            for location in Location.filter_by_type("colalifezambia", location_type):
                supply_point_case = SupplyPointCase.get_by_location(location)
                supply_point_case.location_type = location_type
                supply_point_case.save()
