from django.core.management import BaseCommand
from django.db.models import Count
from casexml.apps.stock.models import StockTransaction, StockReport
from corehq.apps.commtrack.models import StockState
from corehq.apps.hqcase.dbaccessors import \
    get_supply_point_case_in_domain_by_id
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tasks import get_ilsgateway_data_migrations
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

        # migrate
        config = ILSGatewayConfig.for_domain(domain)
        assert config.enabled, 'ilsgateway sync must be configured for this domain'
        endpoint = ILSGatewayEndpoint.from_config(config)
        stock_data_task(domain, endpoint, get_ilsgateway_data_migrations(), config,
                        test_facilities=[ilsgateway_id])


def _cleanup_existing_data(domain, ilsgateway_id):
    case = get_supply_point_case_in_domain_by_id(domain, ilsgateway_id)
    # delete stock transactions
    stock_transactions = StockTransaction.objects.filter(case_id=case._id)
    count = stock_transactions.count()
    if count:
        print 'deleting {} existing StockTransactions'.format(count)
        stock_report_ids = stock_transactions.values_list('report_id', flat=True)
        stock_transactions.delete()

        # and related stock reports
        # todo: this may never be necessary due to the stock transactions deletion signal?
        stock_reports = StockReport.objects.filter(pk__in=stock_report_ids)
        if stock_reports.count():
            report_txn_counts = stock_reports.annotate(txn_count=Count('stocktransaction'))
            for sr in report_txn_counts:
                assert sr.txn_count == 0
            print 'deleting {} existing StockReports'.format(stock_reports.count())
            stock_reports.delete()

    # also clear stock states
    stock_states = StockState.objects.filter(case_id=case._id)
    count = stock_states.count()
    if count:
        print 'deleting {} existing StockStates'.format(count)
        stock_states.delete()
