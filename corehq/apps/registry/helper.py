from django.utils.functional import cached_property

from corehq.apps.registry.exceptions import RegistryNotFound
from corehq.apps.registry.models import DataRegistry


class DataRegistryHelper:
    def __init__(self, current_domain, registry_slug):
        self.current_domain = current_domain
        self.registry_slug = registry_slug

    @cached_property
    def registry(self):
        try:
            return DataRegistry.objects.accessible_to_domain(
                self.current_domain, self.registry_slug
            ).get()
        except DataRegistry.DoesNotExist:
            raise RegistryNotFound(self.registry_slug)

    @property
    def visible_domains(self):
        return {self.current_domain} | self.registry.get_granted_domains(self.current_domain)

    @property
    def participating_domains(self):
        self.registry.check_ownership(self.current_domain)
        return self.registry.get_participating_domains()
