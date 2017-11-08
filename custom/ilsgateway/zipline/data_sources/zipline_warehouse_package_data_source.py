from __future__ import absolute_import
from django.utils.translation import ugettext as _

from corehq.apps.reports.datatables import DataTablesColumn
from custom.ilsgateway.zipline.data_sources.zipline_data_source import ZiplineDataSource
from custom.zipline.models import EmergencyOrderPackage

from custom.ilsgateway.zipline import helpers


class ZiplineWarehousePackageDataSource(ZiplineDataSource):

    @property
    def order_id(self):
        return self.config.order_id

    @property
    def filters(self):
        descendants = self.sql_location.get_descendants(include_self=True)\
            .filter(location_type__administrative=False)\
            .exclude(is_archived=True)\
            .values_list('location_id', flat=True)
        additional_filters = {
            'order__location__location_id__in': descendants
        }

        if self.statuses:
            additional_filters['status__in'] = self.statuses

        order_id = self.order_id
        if order_id:
            additional_filters['order_id'] = order_id

        return dict(
            order__domain=self.domain,
            order__timestamp__range=[self.start_date, self.end_date],
            **additional_filters
        )

    def get_emergency_order_packages(self, start, limit):
        offset = start + limit
        return EmergencyOrderPackage.objects.filter(
            **self.filters
        ).select_related(
            'order',
            'dispatched_status',
            'delivered_status'
        ).order_by('order__timestamp', 'package_number')[start:offset]

    @property
    def columns(self):
        return [
            DataTablesColumn('Order id', help_text=_('unique id assigned to the order by ILSGateway')),
            DataTablesColumn('Location code', help_text=_('the location that corresponds to the health facility')),
            DataTablesColumn('Status',
                             help_text=_('"current status of the transaction (dispatched cancelled delivered)"')),
            DataTablesColumn('Status dispatched', help_text=_('time that uav is launched to delivery site')),
            DataTablesColumn('Status delivered', help_text=_('time that vehicle dropped package')),
            DataTablesColumn('Delivery leadtime', help_text=_('difference between dispatched and delivered')),
            DataTablesColumn('Package number', help_text=_('a sequential number assigned '
                                                           'to each package within an order')),
            DataTablesColumn('Vehicle id', help_text=_('the unique id for the vehicle that is set to be delivered,'
                                                       ' will be repeated based on vehciles at warehouse')),
            DataTablesColumn('Package id', help_text=_('the unique id for the package '
                                                       'that is set to be delivered')),
            DataTablesColumn('Package weight (grams)', help_text=_('calculated weight of'
                                                                   ' the products in the vehicle')),
            DataTablesColumn('Products in package')
        ]

    def get_data(self, start, limit):
        emergency_order_packages = self.get_emergency_order_packages(start, limit)
        rows = []
        for emergency_order_package in emergency_order_packages:
            vehicle_id = ''
            package_id = ''
            if emergency_order_package.dispatched_status:
                vehicle_id = emergency_order_package.dispatched_status.vehicle_id or ''
                package_id = emergency_order_package.dispatched_status.package_id or ''

            delivery_lead_time = ''
            delivered_status = emergency_order_package.delivered_status
            dispatched_status = emergency_order_package.dispatched_status
            if delivered_status and dispatched_status:
                delivery_lead_time = '%.2f' % (
                    (delivered_status.zipline_timestamp - dispatched_status.zipline_timestamp).seconds / 60.0
                )

            rows.append([
                emergency_order_package.order_id,
                emergency_order_package.order.location_code,
                helpers.format_status(emergency_order_package.status),
                helpers.zipline_status_date_or_empty_string(emergency_order_package.dispatched_status),
                helpers.zipline_status_date_or_empty_string(emergency_order_package.delivered_status),
                delivery_lead_time,
                emergency_order_package.package_number,
                vehicle_id,
                package_id,
                emergency_order_package.weight,
                helpers.convert_products_dict_to_list(emergency_order_package.products)
            ])
        return rows

    @property
    def total_count(self):
        return EmergencyOrderPackage.objects.filter(**self.filters).count()
