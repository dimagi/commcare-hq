from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy

from corehq.apps.linked_domain.const import LINKED_MODELS
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class DomainLinkFilter(BaseSingleOptionFilter):
    slug = 'domain_link'
    label = ugettext_lazy('Project Link')
    default_text = None

    @property
    def options(self):
        links = get_linked_domains(self.domain)
        return [
            (str(link.id), link.linked_domain)
            for link in links
        ]


class DomainLinkModelFilter(BaseSingleOptionFilter):
    slug = 'domain_link_model'
    label = ugettext_lazy('Data Model')
    default_text = ugettext_lazy("All")

    @property
    def options(self):
        return list(LINKED_MODELS)
