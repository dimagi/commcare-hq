from django.db.models.aggregates import Sum

from custom.ilsgateway.zipline.data_sources.zipline_data_source import ZiplineDataSource
from custom.zipline.models import EmergencyOrder, EmergencyOrderPackage, EmergencyOrderStatusUpdate
from custom.ilsgateway.zipline import helpers


class SupervisorReportDataSource(ZiplineDataSource):

    @property
    def orders_id(self):
        return self.config.orders_id

    @property
    def filters(self):
        additional_filters = {}
        if self.sql_location.location_type_object.administrative:
            descendants = self.sql_location.get_descendants() \
                .exclude(is_archived=True).values_list('site_code', flat=True)
            additional_filters['order__location_code__in'] = descendants
        else:
            additional_filters['order__location_code'] = self.sql_location.site_code

        if self.statuses:
            additional_filters['status__in'] = self.statuses

        orders_id = filter(lambda x: bool(x), self.orders_id)
        if orders_id:
            additional_filters['order_id__in'] = orders_id

        return dict(
            order__domain=self.domain,
            order__timestamp__range=[self.start_date, self.end_date],
            **additional_filters
        )

    def get_emergency_orders(self, start, limit):
        offset = start + limit
        return EmergencyOrder.objects.filter(**self.filters).select_related('confirmed_status')[start:offset]

    @property
    def total_count(self):
        return EmergencyOrder.objects.filter(**self.filters).count()

    def get_data(self, start, limit):
        emergency_orders = self.get_emergency_orders(start, limit)
        rows = []

        for emergency_order in emergency_orders:
            delivered_products_cost = EmergencyOrderPackage.objects.filter(
                order_id=emergency_order.pk,
                status=EmergencyOrderStatusUpdate.STATUS_DELIVERED
            ).aggregate(sum_cost=Sum('cost'))['sum_cost']
            rows.append([
                helpers.format_date(emergency_order.timestamp),
                emergency_order.location_code,
                emergency_order.status,
                helpers.delivery_lead_time(emergency_order, emergency_order.confirmed_status),
                helpers.status_date_or_empty_string(emergency_order.confirmed_status),
                helpers.convert_products_dict_to_list(emergency_order.products_requested),
                delivered_products_cost,
                helpers.products_requested_not_confirmed(emergency_order)
            ])
        return rows
