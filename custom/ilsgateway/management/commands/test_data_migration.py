from django.core.management import BaseCommand
from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tasks import get_ilsgateway_data_migrations
from custom.ilsgateway.utils import get_supply_point_by_external_id
from custom.logistics.tasks import stock_data_task


class Command(BaseCommand):
    """
    Manually test the stock data migration.
    """

    def handle(self, domain, *args, **options):
        if len(args) == 1:
            ilsgateway_id = args[0]
        else:
            ilsgateway_id = 1166  # defaults to bondenzi: http://ilsgateway.com/tz/facility/1166/

        # cleanup
        _cleanup_existing_data(domain, ilsgateway_id)
        config = ILSGatewayConfig.for_domain(domain)
        assert config.enabled, 'ilsgateway sync must be configured for this domain'
        endpoint = ILSGatewayEndpoint.from_config(config)
        stock_data_task(domain, endpoint, get_ilsgateway_data_migrations(), test_facilities=[ilsgateway_id])


def _cleanup_existing_data(domain, ilsgateway_id):
    case = get_supply_point_by_external_id(domain, ilsgateway_id)
    for model_cls in [StockTransaction, StockState]:
        count = model_cls.objects.filter(case_id=case._id).count()
        if count:
            print 'deleting {} existing {}s'.format(count, model_cls.__name__)
            model_cls.objects.filter(case_id=case._id).delete()
