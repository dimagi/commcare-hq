from __future__ import absolute_import
from corehq.apps.reports.filters.base import BaseMultipleOptionFilter, BaseReportFilter
from custom.zipline.models import EmergencyOrderStatusUpdate


class EmergencyOrderStatusChoiceFilter(BaseMultipleOptionFilter):
    slug = 'statuses'
    label = 'Status'

    @property
    def options(self):
        statuses = dict(EmergencyOrderStatusUpdate.STATUS_CHOICES)
        return [
            (EmergencyOrderStatusUpdate.STATUS_PENDING, statuses[EmergencyOrderStatusUpdate.STATUS_PENDING]),
            (EmergencyOrderStatusUpdate.STATUS_ERROR, statuses[EmergencyOrderStatusUpdate.STATUS_ERROR]),
            (EmergencyOrderStatusUpdate.STATUS_RECEIVED, statuses[EmergencyOrderStatusUpdate.STATUS_RECEIVED]),
            (EmergencyOrderStatusUpdate.STATUS_REJECTED, statuses[EmergencyOrderStatusUpdate.STATUS_REJECTED]),
            (EmergencyOrderStatusUpdate.STATUS_APPROVED, statuses[EmergencyOrderStatusUpdate.STATUS_APPROVED]),
            (EmergencyOrderStatusUpdate.STATUS_CANCELLED, statuses[EmergencyOrderStatusUpdate.STATUS_CANCELLED]),
            (EmergencyOrderStatusUpdate.STATUS_DISPATCHED, statuses[EmergencyOrderStatusUpdate.STATUS_DISPATCHED]),
            (EmergencyOrderStatusUpdate.STATUS_DELIVERED, statuses[EmergencyOrderStatusUpdate.STATUS_DELIVERED]),
            (EmergencyOrderStatusUpdate.STATUS_CONFIRMED, statuses[EmergencyOrderStatusUpdate.STATUS_CONFIRMED]),
            (EmergencyOrderStatusUpdate.STATUS_CANCELLED_BY_USER,
             statuses[EmergencyOrderStatusUpdate.STATUS_CANCELLED_BY_USER]),

        ]


class EmergencyPackageStatusChoiceFilter(EmergencyOrderStatusChoiceFilter):
    @property
    def options(self):
        statuses = dict(EmergencyOrderStatusUpdate.STATUS_CHOICES)
        return [
            (EmergencyOrderStatusUpdate.STATUS_DISPATCHED, statuses[EmergencyOrderStatusUpdate.STATUS_DISPATCHED]),
            (EmergencyOrderStatusUpdate.STATUS_DELIVERED, statuses[EmergencyOrderStatusUpdate.STATUS_DELIVERED]),
            (EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT,
             statuses[EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT]),

        ]


class OrderIdFilter(BaseReportFilter):

    slug = 'order_id'
    label = 'Order id'

    template = 'ilsgateway/filters/order_id_filter.html'

    @property
    def filter_context(self):
        return {
            'value': self.get_value(self.request, self.domain),
            'slug': self.slug,
            'input_css_class': self.css_class
        }
