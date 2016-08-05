from django.core.urlresolvers import reverse

from corehq.apps.reports.filters.base import BaseMultipleOptionFilter
from custom.zipline.models import EmergencyOrderStatusUpdate
from dimagi.utils.decorators.memoized import memoized


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


class OrderIdChoiceFilter(BaseMultipleOptionFilter):

    slug = 'orders_id'
    label = 'Orders id'

    @property
    def filter_context(self):
        context = super(OrderIdChoiceFilter, self).filter_context
        context['endpoint'] = reverse('zipline_orders_view', kwargs={'domain': self.domain})
        return context

    @property
    def pagination_source(self):
        return reverse('zipline_orders_view', kwargs={'domain': self.domain})

    @property
    @memoized
    def selected(self):
        return [
            {'id': pk, 'text': pk}
            for pk in self.request.GET.getlist(self.slug)
            if pk
        ]

    @property
    def options(self):
        return []
