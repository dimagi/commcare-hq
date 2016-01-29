from django.core.management import BaseCommand

from corehq.apps.accounting.models import DefaultProductPlan
from corehq.apps.accounting.subscription_changes import DomainDowngradeStatusHandler
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = ''

    def handle(self, *args, **kwargs):
        domain_names = args
        for domain in filter(lambda domain: domain, map(Domain.get_by_name, domain_names)):
            is_privilege_being_used = {
                priv: _is_domain_using_privilege(domain, priv)
                for priv in DomainDowngradeStatusHandler.privilege_to_response().keys()
            }
            using_privileges = [priv for (priv, is_in_use) in is_privilege_being_used.items() if is_in_use]
            minimum_plan = DefaultProductPlan.get_lowest_edition_by_domain(domain.name, using_privileges)
            print domain.name, is_privilege_being_used, minimum_plan


def _is_domain_using_privilege(domain, privilege):
    if domain.has_privilege(privilege):
        return bool(DomainDowngradeStatusHandler.privilege_to_response()[privilege](domain))
    return False
