from corehq.apps.registry.exceptions import RegistryNotFound, RegistryAccessException
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.utils import RegistryPermissionCheck
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.timer import TimingContext


class DataRegistryHelper:
    def __init__(self, current_domain, registry_slug=None, registry=None):
        self.current_domain = current_domain
        assert any([registry_slug, registry])

        if registry and registry_slug:
            assert registry.slug == registry_slug

        if registry:
            self._registry = registry
            self.registry_slug = registry.slug
        else:
            self.registry_slug = registry_slug
            self._registry = None

    def check_access(self, couch_user):
        checker = RegistryPermissionCheck(self.current_domain, couch_user)
        return checker.can_view_registry_data(self.registry_slug)

    @property
    def registry(self):
        if not self._registry:
            try:
                self._registry = DataRegistry.objects.accessible_to_domain(
                    self.current_domain, self.registry_slug
                ).get()
            except DataRegistry.DoesNotExist:
                raise RegistryNotFound(self.registry_slug)
        return self._registry

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
        from casexml.apps.phone.data_providers.case.livequery import (
            get_live_case_ids_and_indices, PrefetchIndexCaseAccessor
        )

        self.pre_access_check(case.type)
        self.access_check(case)

        # using livequery to get related cases matches the semantics of case claim
        case_ids, indices = get_live_case_ids_and_indices(case.domain, [case.case_id], TimingContext())
        accessor = PrefetchIndexCaseAccessor(CaseAccessors(case.domain), indices)
        case_ids.remove(case.case_id)
        cases = accessor.get_cases(list(case_ids))

        return [case] + cases
