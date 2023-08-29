from django.core.management.base import BaseCommand
from corehq.apps.accounting.models import BillingAccount, Subscription, SubscriptionType
import csv


class Command(BaseCommand):
    help = 'List customer billing accounts and associated software plans'

    def handle(self, *args, **kwargs):
        customer_billing_account = BillingAccount.objects.filter(is_customer_billing_account=True, is_active=True)
        file_path = "/tmp/customer_billing_plans.csv"
        with open(file_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            headers = ["Account", "Domain", "Software Plan", "Type", "Do not invoice",
                       "Start Date", "End Date", "Main Subscription", "Need Update"]
            csvwriter.writerow(headers)

            for account in customer_billing_account:
                subscriptions = Subscription.visible_objects.filter(account=account, is_active=True)
                if len(subscriptions) == 0:
                    csvwriter.writerow([account.name, "", "", "", "", "", "", "", ""])
                else:
                    # Value for csv column Main Subscription
                    csv_main_subscription = ""
                    try:
                        main_subscription = subscriptions.filter(do_not_invoice=False).get()
                        csv_main_subscription = main_subscription.plan_version
                    except Subscription.DoesNotExist:
                        main_subscription = None
                        csv_main_subscription = "No Main Subscription"
                    except Subscription.MultipleObjectsReturned:
                        main_subscription = None
                        csv_main_subscription = "Multiple Main Subscriptions"
                    for subscription in subscriptions:
                        need_update = False
                        if (
                            main_subscription
                            and subscription.plan_version != main_subscription.plan_version
                            and subscription.service_type in (SubscriptionType.PRODUCT,
                                                              SubscriptionType.IMPLEMENTATION)
                        ):
                            need_update = True
                        csvwriter.writerow([
                            account.name,
                            subscription.subscriber.domain,
                            subscription.plan_version,
                            subscription.service_type,
                            subscription.do_not_invoice,
                            subscription.date_start,
                            subscription.date_end,
                            csv_main_subscription,
                            need_update
                        ])
        print(f"File has been saved to {file_path}")
