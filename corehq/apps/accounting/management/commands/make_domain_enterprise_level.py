from django.core.management import BaseCommand
from corehq import Domain
from corehq.apps.accounting.exceptions import NewSubscriptionError
from corehq.apps.accounting.models import (
    BillingAccount,
    SoftwarePlanEdition,
    SoftwarePlanVersion,
    Subscription,
    BillingAccountType)


class Command(BaseCommand):
    help = ('Create a billing account and an enterprise level subscription '
            'for the given domain')

    def handle(self, *args, **options):
        if len(args) != 1:
            print "Invalid arguments: %s" % str(args)
            return
        domain = Domain.get_by_name(args[0])
        if not domain:
            print "Invalid domain name: %s" % args[0]
            return
        account, _ = BillingAccount.get_or_create_account_by_domain(
            domain.name,
            account_type=BillingAccountType.CONTRACT,
            created_by="management command",
        )
        enterprise_plan_version = SoftwarePlanVersion.objects.filter(
            plan__edition=SoftwarePlanEdition.ENTERPRISE
        )[0]
        try:
            subscription = Subscription.new_domain_subscription(
                account,
                domain.name,
                enterprise_plan_version
            )
        except NewSubscriptionError as e:
            print e.message
            return
        subscription.is_active = True
        subscription.save()
        print 'Domain %s has been upgraded to enterprise level.' % domain.name
