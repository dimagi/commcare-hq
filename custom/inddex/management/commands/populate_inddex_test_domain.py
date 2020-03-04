from django.core.management.base import BaseCommand

from corehq.apps.domain.forms import DimagiOnlyEnterpriseForm
from corehq.apps.domain.shortcuts import create_domain
from custom.inddex.example_data.data import INDDEX_DOMAIN, import_data


class Command(BaseCommand):
    help = ("Populate a local inddex-reports domain with some example data to "
            "try out reports")

    def handle(self, **options):
        setup_domain()
        import_data()


def setup_domain():
    domain_obj = create_domain(name=INDDEX_DOMAIN)
    DimagiOnlyEnterpriseForm(domain_obj, 'management@command.com').process_subscription_management()
