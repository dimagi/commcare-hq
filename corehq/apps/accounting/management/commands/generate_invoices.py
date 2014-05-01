from optparse import make_option
from django.core.management import BaseCommand
from corehq.apps.accounting.tasks import generate_invoices


class Command(BaseCommand):
    help = "Generate missing invoices based on today's date"

    option_list = BaseCommand.option_list + (
        make_option('--create', action='store_true', default=False,
                    help='Generate invoices'),
    )

    def handle(self, *args, **options):
        generate_invoices(
            check_existing=True,
            is_test=not options.get('create', False),
        )
