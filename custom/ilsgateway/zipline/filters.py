from corehq.apps.reports.filters.base import BaseMultipleOptionFilter
from custom.zipline.models import EmergencyOrderStatusUpdate


class EmergencyOrderStatusChoiceFilter(BaseMultipleOptionFilter):
    slug = 'statuses'
    label = 'Status'

    @property
    def options(self):
        return [
            (EmergencyOrderStatusUpdate.STATUS_PENDING, EmergencyOrderStatusUpdate.STATUS_PENDING),
            (EmergencyOrderStatusUpdate.STATUS_ERROR, EmergencyOrderStatusUpdate.STATUS_ERROR),
            (EmergencyOrderStatusUpdate.STATUS_RECEIVED, EmergencyOrderStatusUpdate.STATUS_RECEIVED),
            (EmergencyOrderStatusUpdate.STATUS_REJECTED, EmergencyOrderStatusUpdate.STATUS_REJECTED),
            (EmergencyOrderStatusUpdate.STATUS_APPROVED, EmergencyOrderStatusUpdate.STATUS_APPROVED),
            (EmergencyOrderStatusUpdate.STATUS_CANCELLED, EmergencyOrderStatusUpdate.STATUS_CANCELLED),
            (EmergencyOrderStatusUpdate.STATUS_DISPATCHED, EmergencyOrderStatusUpdate.STATUS_DISPATCHED),
            (EmergencyOrderStatusUpdate.STATUS_DELIVERED, EmergencyOrderStatusUpdate.STATUS_DELIVERED),
            (EmergencyOrderStatusUpdate.STATUS_CONFIRMED, EmergencyOrderStatusUpdate.STATUS_CONFIRMED),
            (EmergencyOrderStatusUpdate.STATUS_CANCELLED_BY_USER,
             EmergencyOrderStatusUpdate.STATUS_CANCELLED_BY_USER),

        ]


class EmergencyPackageStatusChoiceFilter(EmergencyOrderStatusChoiceFilter):
    @property
    def options(self):
        return [
            (EmergencyOrderStatusUpdate.STATUS_DISPATCHED, EmergencyOrderStatusUpdate.STATUS_DISPATCHED),
            (EmergencyOrderStatusUpdate.STATUS_DELIVERED, EmergencyOrderStatusUpdate.STATUS_DELIVERED),
            (EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT,
             EmergencyOrderStatusUpdate.STATUS_CANCELLED_IN_FLIGHT),

        ]
