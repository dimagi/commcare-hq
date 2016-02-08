from django.core.management import BaseCommand

from corehq.apps.accounting.models import DefaultProductPlan
from corehq.apps.accounting.subscription_changes import DomainDowngradeStatusHandler
from corehq.apps.domain.models import Domain


class Command(BaseCommand):
    help = 'Print out a CSV containing a table of what features are in use by project space.'

    def handle(self, *args, **kwargs):
        domain_names = args
        privileges = sorted(DomainDowngradeStatusHandler.supported_privileges())
        print ','.join(['Project Space'] + privileges + ['Lowest Plan'])
        for domain in filter(lambda domain: domain, map(Domain.get_by_name, domain_names)):
            is_privilege_being_used = {
                priv: _is_domain_using_privilege(domain, priv)
                for priv in DomainDowngradeStatusHandler.supported_privileges()
            }
            using_privileges = [priv for (priv, is_in_use) in is_privilege_being_used.items() if is_in_use]
            minimum_plan = DefaultProductPlan.get_lowest_edition_by_domain(domain.name, using_privileges)
            print ','.join(
                [domain.name] +
                ['X' if is_privilege_being_used[priv] else '' for priv in privileges] +
                [minimum_plan]
            )


def _is_domain_using_privilege(domain, privilege):
    if domain.has_privilege(privilege):
        return bool(DomainDowngradeStatusHandler.privilege_to_response_function()[privilege](domain))
    return False
