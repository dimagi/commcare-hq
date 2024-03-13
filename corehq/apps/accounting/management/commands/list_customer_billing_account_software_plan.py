from django.core.management.base import BaseCommand
from corehq.apps.accounting.models import BillingAccount, Subscription, SubscriptionType
import csv


class Command(BaseCommand):
    # Always run this command without '--update' first
    # let Ops review the output before running with '--update'
    help = 'List customer billing accounts and associated software plans'

    def add_arguments(self, parser):
        parser.add_argument('--update', action='store_true', default=False,
                            help='Update all software plans (type PRODUCT or IMPLEMENTATION) '
                            'under each billing account to the main billing subscription')

    def handle(self, *args, **kwargs):
        allow_update = kwargs['update']
        customer_billing_accounts = []
        while True:
            account_name = input("Enter a customer billing account name, "
                                 "type 'ALL' for all customer billing account, "
                                 "type 'DONE' when finished:\n")
            if account_name.upper() == 'ALL':
                if allow_update:
                    print("Please specify the exact list of accounts when running with --update"
                          " to avoid accidental update.")
                else:
                    customer_billing_accounts = BillingAccount.objects.filter(
                        is_customer_billing_account=True, is_active=True)
                    break
            elif account_name.upper() == 'DONE':
                break
            else:
                try:
                    account = BillingAccount.objects.get(name=account_name,
                                                         is_active=True, is_customer_billing_account=True)
                except BillingAccount.DoesNotExist:
                    print(f"Customer billing account {account_name} does not exist")
                else:
                    customer_billing_accounts.append(account)

        file_path = "/tmp/customer_billing_plans.csv"
        with open(file_path, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile)
            headers = ["Account", "Domain", "Software Plan", "Type", "Do not invoice",
                       "Start Date", "End Date", "Main Subscription", "Need Update", "Status"]
            csvwriter.writerow(headers)

            for account in customer_billing_accounts:
                subscriptions = Subscription.visible_objects.filter(account=account, is_active=True)
                if len(subscriptions) == 0:
                    csvwriter.writerow([account.name, "", "", "", "", "", "", "", "", ""])
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
                        update_status = ''
                        needs_update = bool(
                            main_subscription
                            and subscription.plan_version != main_subscription.plan_version
                            and subscription.service_type in (SubscriptionType.PRODUCT,
                                                              SubscriptionType.IMPLEMENTATION)
                        )
                        if allow_update and needs_update:
                            try:
                                subscription.upgrade_plan_for_consistency(
                                    new_plan_version=main_subscription.plan_version,
                                    upgrade_note="Upgraded to main billing software plan by command",
                                    web_user=None)
                            except Exception as e:
                                update_status = f"Failed, {e}"
                            else:
                                update_status = "Success"
                        csvwriter.writerow([
                            account.name,
                            subscription.subscriber.domain,
                            subscription.plan_version,
                            subscription.service_type,
                            subscription.do_not_invoice,
                            subscription.date_start,
                            subscription.date_end,
                            csv_main_subscription,
                            needs_update,
                            update_status
                        ])
        print(f"File has been saved to {file_path}")
