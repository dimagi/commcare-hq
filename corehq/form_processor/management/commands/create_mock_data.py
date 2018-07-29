from __future__ import absolute_import, print_function
from __future__ import unicode_literals
from datetime import datetime
from django.core.management.base import BaseCommand
from casexml.apps.case.mock import CaseFactory
from six.moves import range


class Command(BaseCommand):
    help = "Create simple mock data in a domain."

    def add_arguments(self, parser):
        parser.add_argument('domain', help='Domain to create data in.')
        parser.add_argument('count', type=int, help='Number of forms/cases to create.')

    def handle(self, domain, count, **options):
        factory = CaseFactory(domain=domain)
        date_string = datetime.now().isoformat()
        for i in range(count):
            factory.create_case(case_name='mock-data-{}-{}'.format(date_string, i))
        print('successfully created {} cases in domain {} with timestamp {}'.format(count, domain, date_string))
