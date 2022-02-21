from django.core.management.base import BaseCommand

from corehq import toggles
from corehq.apps.domain.models import RESTRICTED_DTE_EXPRESSIONS, Domain


class Command(BaseCommand):
    help = """Adds active DTE expressions(UCR expressions) to the Domain model of all the domains that have
    UCR feature flag turned on"""

    def handle(self, **options):
        values = [val[0] for val in RESTRICTED_DTE_EXPRESSIONS]
        domains = toggles.USER_CONFIGURABLE_REPORTS.get_enabled_domains()
        print(f"Found {len(domains)} domains that has UCR Feature flag enabled")
        for domain in domains:
            print(f"Add permissions for domain {domain}")
            domain_obj = Domain.get_by_name(domain)
            domain_obj.internal.active_dte_expressions = values
            domain_obj.save()
