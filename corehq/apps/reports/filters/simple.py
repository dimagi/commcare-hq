from django.utils.translation import ugettext_lazy
from corehq.apps.reports.filters.base import BaseSimpleFilter


class RepeaterPayloadIdFilter(BaseSimpleFilter):
    slug = "payload_id"
    label = ugettext_lazy("Payload ID")


class SimpleUsername(BaseSimpleFilter):
    slug = 'username'
    label = ugettext_lazy("Username")


class SimpleDomain(BaseSimpleFilter):
    slug = 'domain_name'
    label = ugettext_lazy('Domain')
    help_inline = ugettext_lazy('Optional')
