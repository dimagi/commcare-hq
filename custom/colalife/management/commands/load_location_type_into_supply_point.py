from corehq.apps.locations.models import Location
from django.core.management import BaseCommand

from corehq.form_processor.interfaces.supply import SupplyInterface


class Command(BaseCommand):
    help = 'Store location type with supply point.'

    def handle(self, *args, **options):
        for location_type in ["wholesaler", "retailer"]:
            domain = "colalifezambia"
            for location in Location.filter_by_type(domain, location_type):
                supply_point_case = SupplyInterface(domain).get_by_location(location)
                supply_point_case.location_type = location_type
                supply_point_case.save()
