from datetime import datetime
from django.core.management import BaseCommand
from corehq.apps.locations.models import SQLLocation
from custom.ilsgateway.models import ILSGatewayConfig, ReportRun, SupplyPointStatus, DeliveryGroupReport, \
    SupplyPointWarehouseRecord, OrganizationSummary, ProductAvailabilityData, Alert

from custom.ilsgateway.tasks import report_run
from custom.ilsgateway.tanzania.warehouse import updater


class Command(BaseCommand):
    """
    Manually test the stock data migration.
    """

    def handle(self, domain, *args, **options):
        if len(args) == 1:
            ilsgateway_id = args[0]
        else:
            ilsgateway_id = 1166  # defaults to bondenzi: http://ilsgateway.com/tz/facility/1166/

        # monkey patch the default start date to cover less data
        updater.default_start_date = lambda: datetime(2015, 1, 1)
        config = ILSGatewayConfig.for_domain(domain)
        assert config.enabled, 'ilsgateway sync must be configured for this domain'
        locations = _get_locations_from_ilsgateway_id(domain, ilsgateway_id)
        _clear_data(domain)
        report_run(domain, locations, strict=False)


def _clear_data(domain):
    ReportRun.objects.filter(domain=domain).delete()
    SupplyPointStatus.objects.all().delete()
    DeliveryGroupReport.objects.all().delete()
    SupplyPointWarehouseRecord.objects.all().delete()
    OrganizationSummary.objects.all().delete()
    ProductAvailabilityData.objects.all().delete()
    Alert.objects.all().delete()


def _get_locations_from_ilsgateway_id(domain, ilsgateway_id):
    facility = SQLLocation.objects.get(domain=domain, external_id=ilsgateway_id)
    return [facility.couch_location] + [facility.parent.couch_location] + [facility.parent.parent.couch_location]
