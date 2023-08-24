from django.core.management.base import BaseCommand
from corehq.apps.accounting.models import BillingAccount, Subscription
import csv


class Command(BaseCommand):
    help = 'List customer billing accounts and associated software plans'

    def handle(self, *args, **kwargs):
        customer_billing_account = BillingAccount.objects.filter(is_customer_billing_account=True, is_active=True)
        file_path = "/tmp/customer_billing_plans.csv"
        with open(file_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            headers = ["Account", "Domain", "Software Plan", "Type", "Do not invoice", "Start Date", "End Date"]
            csvwriter.writerow(headers)

            for account in customer_billing_account:
                subscriptions = Subscription.visible_objects.filter(account=account, is_active=True)
                if len(subscriptions) == 0:
                    csvwriter.writerow([account.name, "", "", "", ""])

                else:
                    for subscription in subscriptions:
                        csvwriter.writerow([
                            account.name,
                            subscription.subscriber.domain,
                            str(subscription.plan_version),
                            subscription.service_type,
                            subscription.do_not_invoice,
                            subscription.date_start,
                            subscription.date_end
                        ])
        print(f"File has been saved to {file_path}")
