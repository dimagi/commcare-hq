from django.core.management.base import NoArgsCommand
from corehq.apps.accounting import generator


class Command(NoArgsCommand):

    def handle_noargs(self, **options):
        generator.currency_usd()
        generator.instantiate_subscribable_plans()
