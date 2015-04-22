from django.core.management import BaseCommand
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tasks import report_run


class Command(BaseCommand):
    """
    Manually test the stock data migration.
    """

    def handle(self, domain, *args, **options):
        if len(args) == 1:
            ilsgateway_id = args[0]
        else:
            ilsgateway_id = 1166  # defaults to bondenzi: http://ilsgateway.com/tz/facility/1166/

        config = ILSGatewayConfig.for_domain(domain)
        assert config.enabled, 'ilsgateway sync must be configured for this domain'
        locations = _get_locations_from_ilsgateway_id(domain, ilsgateway_id)
        report_run(domain, locations)


def _get_locations_from_ilsgateway_id(domain, ilsgateway_id):
    facility = SQLLocation.objects.get(domain=domain, external_id=ilsgateway_id)
    return [facility.couch_location] + [facility.parent.couch_location] + [facility.parent.parent.couch_location]
