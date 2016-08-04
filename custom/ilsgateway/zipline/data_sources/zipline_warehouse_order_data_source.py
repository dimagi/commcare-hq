from custom.ilsgateway.zipline.data_sources.zipline_data_source import ZiplineDataSource
from custom.zipline.models import EmergencyOrder
from custom.ilsgateway.zipline import helpers


class ZiplineWarehouseOrderDataSource(ZiplineDataSource):

    def get_emergency_orders(self, start, limit):
        offset = start + limit

        additional_filters = {}
        if self.sql_location.location_type_object.administrative:
            descendants = self.sql_location.get_descendants()\
                .exclude(is_archived=True).values_list('site_code', flat=True)
            additional_filters['location_code__in'] = descendants
        else:
            additional_filters['location_code'] = self.sql_location.site_code

        if self.statuses:
            additional_filters['status__in'] = self.statuses

        return EmergencyOrder.objects.filter(
            domain=self.domain,
            timestamp__range=[self.start_date, self.end_date],
            **additional_filters
        ).select_related(
            'received_status',
            'rejected_status',
            'cancelled_status',
            'approved_status',
            'dispatched_status',
            'delivered_status'
        )[start:offset]

    def get_data(self, start, limit):
        emergency_orders = self.get_emergency_orders(start, limit)
        rows = []
        for emergency_order in emergency_orders:
            rows.append([
                emergency_order.pk,
                emergency_order.requesting_phone_number,
                helpers.format_date(emergency_order.timestamp),
                emergency_order.location_code,
                emergency_order.status,
                helpers.delivery_lead_time(emergency_order.received_status, emergency_order.delivered_status),
                emergency_order.zipline_request_attempts,
                helpers.status_date_or_empty_string(emergency_order.received_status),
                helpers.status_date_or_empty_string(emergency_order.rejected_status),
                helpers.status_date_or_empty_string(emergency_order.cancelled_status),
                helpers.status_date_or_empty_string(emergency_order.approved_status),
                helpers.status_date_or_empty_string(emergency_order.dispatched_status),
                helpers.status_date_or_empty_string(emergency_order.delivered_status),
                helpers.products_requested(emergency_order),
                helpers.products_delivered(emergency_order),
                helpers.products_requested_not_confirmed(emergency_order)
            ])
        return rows
