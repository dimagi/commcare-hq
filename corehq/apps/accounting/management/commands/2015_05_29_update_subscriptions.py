from django.core.management import BaseCommand
from corehq.apps.accounting.models import BillingAccount, Subscription, SubscriptionType, ProBonoStatus, EntryPoint
import csv
import re


class Command(BaseCommand):
    help = ("Updates service type, entry point, and pro bono status based on given CSV file")

    def handle(self, *args, **options):
        if len(args) != 1:
            print "Invalid arguments: %s" % str(args)
            return

        completed = 0
        total = 0
        filename = args[0]
        with open(filename) as f:
            reader = csv.reader(f)
            reader.next()
            for row in reader:
                total = total + 1
                domain = row[0]
                plan_version, subscription = Subscription.get_subscribed_plan_by_domain(domain)
                if subscription is None:
                    print "Could not find Subscription for %s" % domain

                account = BillingAccount.get_account_by_domain(domain)
                if account is None:
                    print "Could not find BillingAccount for %s" % domain

                if account is not None and subscription is not None:
                    '''
                    service_type = self.normalize(row[1])  # self service, contracted, or not set
                    if service_type == "selfservice":
                        #print "%s service_type => SELF_SERVICE" % domain
                        subscription.service_type = SubscriptionType.SELF_SERVICE
                    elif service_type == "contracted":
                        #print "%s service_type => CONTRACTED" % domain
                        subscription.service_type = SubscriptionType.CONTRACTED
                    elif service_type == "notset":
                        #print "%s service_type => NOT_SET" % domain
                        subscription.service_type = SubscriptionType.NOT_SET
                    else:
                        pass
                        #print "Skipping service type for %s" % domain

                    entry_point = self.normalize(row[2])  # yes if self starter, might be missing
                    if entry_point == "yes":
                        #print "%s entry_point => SELF_STARTED" % domain
                        account.entry_point = EntryPoint.SELF_STARTED
                    elif entry_point == "no":
                        #print "%s entry_point => CONTRACTED" % domain
                        account.entry_point = EntryPoint.CONTRACTED
                    else:
                        #print "Skipping entry point for %s" % domain
                        pass
                    '''

                    pro_bono_status = self.normalize(row[3])  # yes/no
                    if pro_bono_status == "yes":
                        #print "%s pro_bono_status => YES" % domain
                        subscription.pro_bono_status = ProBonoStatus.YES
                    elif pro_bono_status == "discounted":
                        #print "%s pro_bono_status => DISCOUNTED" % domain
                        subscription.pro_bono_status = ProBonoStatus.DISCOUNTED
                    else:
                        #print "%s pro_bono_status => NO" % domain
                        subscription.pro_bono_status = ProBonoStatus.NO

                    '''print "setting %s's service_type=%s, entry_point=%s, pro_bono=%s" % (
                        domain, subscription.service_type, account.entry_point, subscription.pro_bono_status
                    )'''

                    subscription.save()
                    account.save()
                    completed = completed + 1

        print "Completed %i of %i domains" % (completed, total)

    def normalize(self, str):
        return re.sub(r'[^a-z]', "", str.lower())
