from optparse import make_option
import datetime
from django.core.management import BaseCommand
from corehq.apps.accounting.tasks import generate_invoices


class Command(BaseCommand):
    help = ("Generate missing invoices based on the given date in YYYY-MM-DD "
            "format")

    option_list = BaseCommand.option_list + (
        make_option('--create', action='store_true', default=False,
                    help='Generate invoices'),
    )

    def handle(self, *args, **options):
        generate_invoices(
            based_on_date=datetime.date(*[int(_) for _ in args[0:3]]),
            check_existing=True,
            is_test=not options.get('create', False),
        )
