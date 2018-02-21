from __future__ import absolute_import
from __future__ import division
from django.db.models.aggregates import Sum
from django.utils.translation import ugettext_lazy as _

from corehq.apps.reports.datatables import DataTablesColumn
from custom.ilsgateway.zipline.data_sources.zipline_data_source import ZiplineDataSource
from custom.zipline.models import EmergencyOrder, EmergencyOrderPackage, EmergencyOrderStatusUpdate
from custom.ilsgateway.zipline import helpers


class SupervisorReportDataSource(ZiplineDataSource):

    @property
    def order_id(self):
        return self.config.order_id

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

        order_id = self.order_id
        if order_id:
            additional_filters['pk'] = order_id

        return dict(
            domain=self.domain,
            timestamp__range=[self.start_date, self.end_date],
            **additional_filters
        )

    def get_emergency_orders(self, start, limit):
        offset = start + limit
        return EmergencyOrder.objects.filter(
            **self.filters
        ).select_related('confirmed_status').order_by('timestamp')[start:offset]

    @property
    def total_count(self):
        return EmergencyOrder.objects.filter(**self.filters).count()

    @property
    def columns(self):
        return [
            DataTablesColumn('date', help_text=_('timestamp for receipt of incoming emg request, automatic')),
            DataTablesColumn('location code', help_text=_('the location that corresponds to the health facility')),
            DataTablesColumn('status', help_text=_('current status of the transaction (rejected, cancelled, '
                                                   'cancelled by user, received, approved, dispatched, delivered, '
                                                   'confirmed)')),
            DataTablesColumn('total delivery time', help_text=_('time between emg status and rec status, '
                                                                'total time to resupply  in minutes')),
            DataTablesColumn('confirmation timestamp', help_text=_('timestamp for receipt of rec confirmation')),
            DataTablesColumn('emergency order request', help_text=_('structured string with product long codes'
                                                                    ' (for example, 10010203MD) and quantities'
                                                                    ' for products requested in emg request ')),
            DataTablesColumn('delivered products cost', help_text=_('value of products dropped to the'
                                                                    ' health facility, tanzanian shillings')),
            DataTablesColumn('products requested and not confirmed',
                             help_text=_('structured string with products '
                                         'that were not confirmed based on the request'))
        ]

    def get_data(self, start, limit):
        emergency_orders = self.get_emergency_orders(start, limit)
        rows = []

        for emergency_order in emergency_orders:
            delivered_products_cost = EmergencyOrderPackage.objects.filter(
                order_id=emergency_order.pk,
                status=EmergencyOrderStatusUpdate.STATUS_DELIVERED
            ).aggregate(sum_cost=Sum('cost'))['sum_cost']

            delivery_lead_time = ''
            confirmed_status = emergency_order.confirmed_status
            if confirmed_status:
                delivery_lead_time = '%.2f' % (
                    (confirmed_status.timestamp - emergency_order.timestamp).seconds / 60.0
                )

            rows.append([
                helpers.format_date(emergency_order.timestamp),
                emergency_order.location_code,
                helpers.format_status(emergency_order.status),
                delivery_lead_time,
                helpers.status_date_or_empty_string(emergency_order.confirmed_status),
                helpers.convert_products_dict_to_list(emergency_order.products_requested),
                delivered_products_cost,
                helpers.products_requested_not_confirmed(emergency_order)
            ])
        return rows
