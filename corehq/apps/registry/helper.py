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

    def pre_access_check(self, case_type):
        if case_type not in self.registry.wrapped_schema.case_types:
            raise RegistryAccessException(f"'{case_type}' not available in registry")

    def access_check(self, case):
        if case.domain not in self.visible_domains:
            raise RegistryAccessException("Data not available in registry")

    def get_case(self, case_id, case_type, user, application):
        from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL

        self.pre_access_check(case_type)
        case = CaseAccessorSQL.get_case(case_id)
        if case.type != case_type:
            raise CaseNotFound("Case type mismatch")

        self.access_check(case)
        self.log_data_access(user, case.domain, application, filters={
            "case_type": case_type,
            "case_id": case_id
        })
        return case

    def get_case_hierarchy(self, case):
        self.pre_access_check(case.type)
        self.access_check(case)

        return _get_case_ancestors(case) + [case] + _get_case_descendants(case)


def _get_case_descendants(case):
    from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
    descendants = []
    seen = set()
    case_ids = {case.case_id}
    while case_ids:
        seen.update(case_ids)
        new_cases = CaseAccessorSQL.get_reverse_indexed_cases(case.domain, list(case_ids), is_closed=False)
        case_ids = {case.case_id for case in new_cases} - seen
        descendants.extend(new_cases)
    return descendants


def _get_case_ancestors(case):
    from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL

    ancestors = []
    indices = case.live_indices
    while indices:
        case_ids = list({index.referenced_id for index in indices})
        indices = CaseAccessorSQL.get_all_indices(case.domain, case_ids)
        parents = CaseAccessorSQL.get_cases(case_ids, prefetched_indices=indices)
        ancestors.extend(parents)

    return ancestors
