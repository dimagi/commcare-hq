from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django.core.management import BaseCommand

from corehq.motech.dhis2.tasks import send_datasets


class Command(BaseCommand):
    """
    Manually send datasets for a project assuming it was run at a date in the past
    """

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument('send_date', help="YYYY-MM-DD")

    def handle(self, domain_name, send_date, **options):
        send_date = datetime.strptime(send_date, '%Y-%m-%d')
        print("Sending dataset")
        send_datasets(domain_name, send_now=True, send_date=send_date)
