from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from django.core.management import BaseCommand

from io import open

from csv342 import csv

from corehq.apps.accounting.models import Subscription


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('input_filename')
        parser.add_argument('output_filename')

    def handle(self, input_filename, output_filename, **options):
        with open(output_filename, 'wb') as output_file:
            writer = csv.writer(output_file)
            writer.writerow([
                'Export ID', 'Project Space', 'Export Size (bytes)', 'Export Format', '# Rows', '# Columns',
                'Software Plan Name', 'Software Plan Edition', 'Monthly Fee'
            ])
            with open(input_filename, 'r') as input_file:
                reader = csv.reader(input_file)
                for row in list(reader)[1:]:
                    domain_name = row[1]
                    active_subscription = Subscription.get_active_subscription_by_domain(domain_name)
                    if active_subscription:
                        plan_version = active_subscription.plan_version
                        plan = plan_version.plan
                        row.append(plan.name)
                        row.append(plan.edition)
                        row.append(plan_version.product_rate.monthly_fee)
                    else:
                        row.extend(['', '', ''])
                    writer.writerow(row)
