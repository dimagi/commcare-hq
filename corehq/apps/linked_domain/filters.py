from django.utils.translation import gettext_lazy

from corehq.apps.linked_domain.const import ALL_LINKED_MODELS, SUPERUSER_DATA_MODELS
from corehq.apps.linked_domain.dbaccessors import get_linked_domains
from corehq.apps.reports.filters.base import BaseSingleOptionFilter


class DomainLinkFilter(BaseSingleOptionFilter):
    slug = 'domain_link'
    label = gettext_lazy('Project Space Link')
    default_text = None

    @property
    def options(self):
        links = get_linked_domains(self.domain, include_deleted=True)
        return [
            (str(link.id), link.linked_domain)
            for link in links
        ]


class DomainLinkModelFilter(BaseSingleOptionFilter):
    slug = 'domain_link_model'
    label = gettext_lazy('Content')
    default_text = gettext_lazy("All")

    @property
    def options(self):
        if self.request.couch_user.is_superuser:
            return list(ALL_LINKED_MODELS)
        return list(set(ALL_LINKED_MODELS) - set(SUPERUSER_DATA_MODELS))
