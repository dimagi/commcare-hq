from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import json
from collections import defaultdict

from django.core.management import BaseCommand

from corehq.apps.accounting.invoicing import LineItemFactory
from corehq.apps.accounting.models import CustomerInvoice, SoftwarePlanVersion


class Command(BaseCommand):

    def handle(self, *args, **options):
        invoice_to_plan_version_to_domains = defaultdict(dict)
        for invoice in CustomerInvoice.objects.order_by('id'):
            for plan_version in SoftwarePlanVersion.objects.filter(
                id__in=invoice.subscriptions.values('plan_version__id')
            ).order_by('id'):
                sample_subscription = invoice.subscriptions.filter(plan_version=plan_version)
                factory = LineItemFactory(sample_subscription, None, invoice)
                invoice_to_plan_version_to_domains[invoice.id][plan_version.id] = factory.subscribed_domains
        print(json.dumps(invoice_to_plan_version_to_domains))

