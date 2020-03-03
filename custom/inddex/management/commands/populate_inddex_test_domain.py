from django.core.management.base import BaseCommand

from corehq.apps.domain.forms import DimagiOnlyEnterpriseForm
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.tasks import rebuild_indicators
from custom.inddex.example_data.data import INDDEX_DOMAIN, import_data


class Command(BaseCommand):
    help = ("Populate a local inddex-reports domain with some example data to "
            "try out reports")

    def handle(self, **options):
        setup_domain()
        import_data()
        rebuild_datasource()


def setup_domain():
    domain_obj = create_domain(name=INDDEX_DOMAIN)
    DimagiOnlyEnterpriseForm(domain_obj, 'management@command.com').process_subscription_management()


def rebuild_datasource():
    config_id = StaticDataSourceConfiguration.get_doc_id(INDDEX_DOMAIN, 'food_consumption_indicators')
    rebuild_indicators(config_id, source='populate_inddex_test_domain')
