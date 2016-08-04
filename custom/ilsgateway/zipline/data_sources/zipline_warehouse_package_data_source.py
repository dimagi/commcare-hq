from custom.ilsgateway.zipline.data_sources.zipline_data_source import ZiplineDataSource
from custom.zipline.models import EmergencyOrderPackage

from custom.ilsgateway.zipline import helpers

class ZiplineWarehousePackageDataSource(ZiplineDataSource):

    @property
    def order_id(self):
        return self.config.order_id

    def get_emergency_order_packages(self, start, limit):
        offset = start + limit
        additional_filters = {}
        if self.sql_location.location_type_object.administrative:
            descendants = self.sql_location.get_descendants() \
                .exclude(is_archived=True).values_list('site_code', flat=True)
            additional_filters['order__location_code__in'] = descendants
        else:
            additional_filters['order__location_code'] = self.sql_location.site_code

        if self.statuses:
            additional_filters['status__in'] = self.statuses

        if self.order_id:
            additional_filters['order_id'] = self.order_id

        return EmergencyOrderPackage.objects.filter(
            order__domain=self.domain,
            order__timestamp__range=[self.start_date, self.end_date],
            **additional_filters
        )[start:offset]

    def get_data(self, start, limit):
        emergency_order_packages = self.get_emergency_order_packages(start, limit)
        rows = []
        for emergency_order_package in emergency_order_packages:
            vehicle_id = ''
            package_id = ''
            if emergency_order_package.dispatched_status:
                vehicle_id = emergency_order_package.dispatched_status.vehicle_id or ''
                package_id = emergency_order_package.dispatched_status.package_id or ''

            rows.append([
                emergency_order_package.order_id,
                emergency_order_package.order.location_code,
                emergency_order_package.status,
                helpers.status_date_or_empty_string(emergency_order_package.dispatched_status),
                helpers.status_date_or_empty_string(emergency_order_package.delivered_status),
                helpers.delivery_lead_time(emergency_order_package.dispatched_status,
                                           emergency_order_package.delivered_status),
                emergency_order_package.package_number,
                vehicle_id,
                package_id,
                emergency_order_package.weight,
                helpers.convert_products_dict_to_list(emergency_order_package.products)
            ])
        return rows
