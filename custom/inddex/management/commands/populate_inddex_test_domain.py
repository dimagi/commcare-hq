from django.core.management.base import BaseCommand

from corehq.apps.domain.forms import DimagiOnlyEnterpriseForm
from corehq.apps.domain.shortcuts import create_domain
from custom.inddex.example_data.data import populate_inddex_domain


class Command(BaseCommand):
    help = ("Populate a local inddex-reports domain with some example data to "
            "try out reports")
    INDDEX_DOMAIN = 'inddex-reports'

    def handle(self, **options):
        setup_domain(self.INDDEX_DOMAIN)
        populate_inddex_domain(self.INDDEX_DOMAIN)


def setup_domain(domain):
    domain_obj = create_domain(name=domain)
    DimagiOnlyEnterpriseForm(domain_obj, 'management@command.com').process_subscription_management()
