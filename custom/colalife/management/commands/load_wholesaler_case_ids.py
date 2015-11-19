from corehq.apps.locations.models import Location
from django.core.management import BaseCommand

from corehq.form_processor.interfaces.supply import SupplyInterface


class Command(BaseCommand):
    help = 'Assign wholesaler case IDs to child cases.'

    def handle(self, *args, **options):
        domain = "colalifezambia"
        interface = SupplyInterface(domain)
        for retailer_location in Location.filter_by_type(domain, "retailer"):
            retailer_case = interface.get_by_location(retailer_location)
            wholesaler_location = retailer_location.parent
            wholesaler_case = interface.get_by_location(
                wholesaler_location
            )
            retailer_case.wholesaler_case_id = wholesaler_case._id
            retailer_case.save()
