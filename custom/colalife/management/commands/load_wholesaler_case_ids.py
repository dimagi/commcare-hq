from corehq.apps.commtrack.models import SupplyPointCase
from corehq.apps.locations.models import Location
from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Assign wholesaler case IDs to child cases.'

    def handle(self, *args, **options):
        for retailer_location in Location.filter_by_type(
                "colalifezambia", "retailer"):
            retailer_case = SupplyPointCase.get_by_location(retailer_location)
            wholesaler_location = retailer_location.parent
            wholesaler_case = SupplyPointCase.get_by_location(
                wholesaler_location
            )
            retailer_case.wholesaler_case_id = wholesaler_case._id
            retailer_case.save()
