import itertools
from operator import attrgetter

from corehq.apps.registry.exceptions import RegistryNotFound, RegistryAccessException
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.utils import RegistryPermissionCheck
from corehq.form_processor.models import CommCareCase


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

    def get_case(self, case_id, couch_user, accessing_object):
        """
        :param accessing_object: object that is calling 'get_case'.
            See ``corehq.apps.registry.models.RegistryAuditHelper.data_accessed``
        :return:
        """
        case = CommCareCase.objects.get_case(case_id)
        self.check_data_access(couch_user, [case.type], case.domain)
        self.log_data_access(couch_user.get_django_user(), case.domain, accessing_object, filters={
            "case_type": case.type,
            "case_id": case_id
        })
        return case

    def get_multi_domain_case_hierarchy(self, couch_user, cases):
        """Get the combined case hierarchy for a list of cases that spans multiple domains"""
        all_cases = list(itertools.chain.from_iterable(
            self.get_case_hierarchy(domain, couch_user, list(domain_cases))
            for domain, domain_cases in itertools.groupby(cases, key=attrgetter("domain"))
        ))
        return all_cases

    def get_case_hierarchy(self, domain, couch_user, cases):
        """Get the combined case hierarchy for the input cases"""
        from casexml.apps.phone.data_providers.case.livequery import get_case_hierarchy
        self.check_data_access(couch_user, [case.type for case in cases], domain)
        return get_case_hierarchy(domain, cases)

    def check_data_access(self, couch_user, case_types, case_domain=None):
        """Perform all checks for data access.
        Will raise a RegistryAccessException if access should be denied.
        """
        for case_type in case_types:
            self._check_case_type_in_registry(case_type)
        self._check_user_has_access(couch_user, case_domain)
        if case_domain is not None:
            self._check_domain_is_visible(case_domain)

    def _check_user_has_access(self, couch_user, case_domain=None):
        if case_domain and self.current_domain == case_domain:
            # always allow access data in the current domain
            return

        checker = RegistryPermissionCheck(self.current_domain, couch_user)
        if not checker.can_view_registry_data(self.registry_slug):
            raise RegistryAccessException("User not permitted to access registry data")

    def _check_case_type_in_registry(self, case_type):
        if case_type not in self.registry.wrapped_schema.case_types:
            raise RegistryAccessException(f"'{case_type}' not available in registry")

    def _check_domain_is_visible(self, domain):
        if domain not in self.visible_domains:
            raise RegistryAccessException("Data not available in registry")
