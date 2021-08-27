from django.utils.functional import cached_property

from corehq.apps.registry.exceptions import RegistryNotFound, RegistryAccessException
from corehq.apps.registry.models import DataRegistry
from corehq.form_processor.exceptions import CaseNotFound


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

    def log_data_access(self, user, domain, related_object, filters=None):
        self.registry.logger.data_accessed(user, domain, related_object, filters)

    def get_case(self, case_id, case_type, user, application):
        if case_type not in self.registry.wrapped_schema.case_types:
            raise RegistryAccessException(f"'{case_type}' not available in registry")

        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
        case = CaseAccessorSQL.get_case(case_id)
        if case.type != case_type:
            raise CaseNotFound("Case type mismatch")

        if case.domain not in self.visible_domains:
            raise RegistryAccessException("Data not available in registry")

        self.log_data_access(user, case.domain, application, filters={
            "case_type": case_type,
            "case_id": case_id
        })
        return case
