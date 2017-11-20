from __future__ import absolute_import
from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesColumn
from custom.ilsgateway.zipline.data_sources.zipline_data_source import ZiplineDataSource
from custom.zipline.models import EmergencyOrder
from custom.ilsgateway.zipline import helpers


class ZiplineWarehouseOrderDataSource(ZiplineDataSource):

    @property
    def filters(self):
        descendants = self.sql_location.get_descendants(include_self=True) \
            .filter(location_type__administrative=False) \
            .exclude(is_archived=True) \
            .values_list('location_id', flat=True)
        additional_filters = {
            'location__location_id__in': descendants
        }

        if self.statuses:
            additional_filters['status__in'] = self.statuses

        return dict(
            domain=self.domain,
            timestamp__range=[self.start_date, self.end_date],
            **additional_filters
        )

    def get_emergency_orders(self, start, limit):
        offset = start + limit
        return EmergencyOrder.objects.filter(**self.filters).select_related(
            'received_status',
            'rejected_status',
            'cancelled_status',
            'approved_status',
            'dispatched_status',
            'delivered_status'
        ).order_by('timestamp')[start:offset]

    @property
    def total_count(self):
        return EmergencyOrder.objects.filter(**self.filters).count()

    @property
    def columns(self):
        return [
            DataTablesColumn('order id', help_text=_('unique identifier for each order assigned by ILSGateway')),
            DataTablesColumn('phone number', help_text=_('phone number that submitted the emg request')),
            DataTablesColumn('date', help_text=_('timestamp for receipt of incoming emg request, automatic')),
            DataTablesColumn('location code', help_text=_('the location that corresponds to the health facility')),
            DataTablesColumn('status', help_text=_('current status of the transaction (rejected, cancelled, '
                                                   'cancelled by user, received, approved, dispatched, delivered, '
                                                   'confirmed)')),
            DataTablesColumn('delivery lead time', help_text=_('time between Request to Zipline and delivery '
                                                               'completed, in minutes (Time for zipline '
                                                               'to get request and then to deliver)')),
            DataTablesColumn('Request Attempts', help_text=_('the number of times ILS gateway '
                                                             'tried to submit a request to the zipline API')),
            DataTablesColumn('status.received', help_text=_('timestamp of received status '
                                                            '(request forwarded to zipline)')),
            DataTablesColumn('status.rejected', help_text=_('timestamp of rejected status '
                                                            '(request forwarded to zipline and zipline rejects)')),
            DataTablesColumn('status.cancelled', help_text=_('timestamp from Zipine status update '
                                                             'if request is closed (cancelled) at level 3. ')),
            DataTablesColumn('status.approved', help_text=_('timestamp for approval of emg '
                                                            'request by Zipline warehouse, automated')),
            DataTablesColumn('status.dispatched', help_text=_('timestamp of dispatch of first vehicle')),
            DataTablesColumn('status.delivered', help_text=_('time stamp for delivery of final vehicle')),
            DataTablesColumn('products requested', help_text=_('structured string with product long codes '
                                                               '(for example, 10010203MD) and quantities '
                                                               'for products requested in emg request ')),
            DataTablesColumn('products delivered', help_text=_('structured string with product '
                                                               'codes for products delivered by zipline')),
            DataTablesColumn('products requested and not confirmed',
                             help_text=_('structured string with products '
                                         'that were not confirmed based on the request'))
        ]

    def get_data(self, start, limit):
        emergency_orders = self.get_emergency_orders(start, limit)
        rows = []

        for emergency_order in emergency_orders:
            delivery_lead_time = ''
            delivered_status = emergency_order.delivered_status
            received_status = emergency_order.received_status
            if delivered_status and received_status:
                delivery_lead_time = '%.2f' % (
                    (delivered_status.zipline_timestamp - received_status.timestamp).seconds / 60.0
                )

            rows.append([
                emergency_order.pk,
                emergency_order.requesting_phone_number,
                helpers.format_date(emergency_order.timestamp),
                emergency_order.location_code,
                helpers.format_status(emergency_order.status),
                delivery_lead_time,
                emergency_order.zipline_request_attempts,
                helpers.status_date_or_empty_string(emergency_order.received_status),
                helpers.status_date_or_empty_string(emergency_order.rejected_status),
                helpers.zipline_status_date_or_empty_string(emergency_order.cancelled_status),
                helpers.zipline_status_date_or_empty_string(emergency_order.approved_status),
                helpers.zipline_status_date_or_empty_string(emergency_order.dispatched_status),
                helpers.zipline_status_date_or_empty_string(emergency_order.delivered_status),
                helpers.products_requested(emergency_order),
                helpers.products_delivered(emergency_order),
                helpers.products_requested_not_confirmed(emergency_order)
            ])
        return rows
