from django.utils.translation import ugettext_lazy
from corehq.apps.reports.filters.base import BaseSimpleFilter


class RepeaterPayloadIdFilter(BaseSimpleFilter):
    slug = "payload_id"
    label = ugettext_lazy("Payload ID")
