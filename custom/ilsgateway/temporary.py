from django.db import connection
from custom.ilsgateway.api import ILSGatewayEndpoint
from custom.ilsgateway.models import ILSGatewayConfig, SupplyPointStatus, DeliveryGroupReport
from custom.logistics.models import StockDataCheckpoint


def fix_stock_data(domain):
    start_date = '2015-07-01'
    end_date = StockDataCheckpoint.objects.get(domain=domain).date.strftime('%Y-%m-%d')
    with connection.cursor() as c:
        c.execute(
            'DELETE FROM ilsgateway_supplypointstatus WHERE location_id IN '
            '(SELECT location_id FROM locations_sqllocation WHERE domain=%s) AND status_date BETWEEN %s AND %s',
            [domain, start_date, end_date]
        )

        c.execute(
            'DELETE FROM ilsgateway_deliverygroupreport WHERE location_id IN '
            '(SELECT location_id FROM locations_sqllocation WHERE domain=%s) AND report_date BETWEEN %s AND %s',
            [domain, start_date, end_date]
        )

        c.execute(
            "DELETE FROM ilsgateway_groupsummary WHERE org_summary_id IN "
            "(SELECT id FROM ilsgateway_organizationsummary WHERE location_id IN "
            "(SELECT location_id FROM locations_sqllocation WHERE domain=%s) AND date BETWEEN %s AND %s)",
            [domain, start_date, end_date]
        )

        c.execute(
            "DELETE FROM ilsgateway_organizationsummary WHERE location_id IN "
            "(SELECT location_id FROM locations_sqllocation WHERE domain=%s AND date BETWEEN %s AND %s)",
            [domain, start_date, end_date]
        )

    config = ILSGatewayConfig.for_domain(domain)
    endpoint = ILSGatewayEndpoint.from_config(config)

    filters = {'status_date__gte': start_date, 'status_date__lte': end_date}

    offset = 0
    _, statuses = endpoint.get_supplypointstatuses(domain, filters=filters, limit=1000, offset=offset)
    while statuses:
        for status in statuses:
            try:
                SupplyPointStatus.objects.get(external_id=status.external_id, location_id=status.location_id)
            except SupplyPointStatus.DoesNotExist:
                status.save()
        offset += 1000
        _, statuses = endpoint.get_supplypointstatuses(domain, filters=filters, limit=1000, offset=offset)

    filters = {'report_date__gte': start_date, 'report_date__lte': end_date}

    offset = 0
    _, reports = endpoint.get_deliverygroupreports(domain, filters=filters, limit=1000, offset=offset)
    while reports:
        for report in reports:
            try:
                DeliveryGroupReport.objects.get(external_id=report.external_id, location_id=report.location_id)
            except DeliveryGroupReport.DoesNotExist:
                report.save()
        offset += 1000
        _, reports = endpoint.get_deliverygroupreports(domain, filters=filters, limit=1000, offset=offset)
