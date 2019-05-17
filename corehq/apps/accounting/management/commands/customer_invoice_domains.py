from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import csv342 as csv
from io import open

from django.core.management import BaseCommand

from corehq.apps.accounting.invoicing import SmsLineItemFactory, UserLineItemFactory
from corehq.apps.accounting.models import CustomerInvoice, SoftwarePlanVersion, FeatureType


class Command(BaseCommand):

    def handle(self, *args, **options):
        with open('customer_invoices.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Customer Invoice ID',
                'Original Number of Users',
                'Original SMS Cost',
                'Correct Number of Users',
                'Correct SMS Cost',
            ])

            for invoice in CustomerInvoice.objects.order_by('id'):
                plan_version_query = SoftwarePlanVersion.objects.filter(
                    id__in=invoice.subscriptions.values('plan_version__id')
                )
                assert len(plan_version_query) == 1, len(plan_version_query)
                plan_version = plan_version_query[0]
                sample_subscription = invoice.subscriptions.filter(plan_version=plan_version)[0]
                sms_factory = SmsLineItemFactory(sample_subscription, None, invoice)
                user_factory = UserLineItemFactory(sample_subscription, None, invoice)
                writer.writerow([
                    invoice.id,
                    invoice.lineitem_set.filter(feature_rate__feature__feature_type=FeatureType.USER)[0].quantity,
                    invoice.lineitem_set.filter(feature_rate__feature__feature_type=FeatureType.SMS)[0].unit_cost,
                    user_factory.num_excess_users_over_period,
                    sms_factory.unit_cost,
                ])
