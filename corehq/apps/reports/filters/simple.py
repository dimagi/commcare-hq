from django.utils.translation import gettext_lazy

from corehq.apps.reports.filters.base import BaseSimpleFilter


class RepeaterPayloadIdFilter(BaseSimpleFilter):
    slug = "payload_id"
    label = gettext_lazy("Payload ID")


class SimpleUsername(BaseSimpleFilter):
    slug = 'username'
    label = gettext_lazy("Username")


class SimpleDomain(BaseSimpleFilter):
    slug = 'domain_name'
    label = gettext_lazy('Domain')
    help_inline = gettext_lazy('Optional')


class SimpleSearch(BaseSimpleFilter):
    slug = 'search_string'
    label = gettext_lazy('Search')
