from django.core.management import BaseCommand
from corehq.apps.domain.models import Domain
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

        plan_version, subscription = Subscription.get_subscribed_plan_by_domain(domain.name)
        if plan_version.plan.edition == SoftwarePlanEdition.ENTERPRISE:
            print "Domain %s is already enterprise level" % domain.name
            return

        if subscription:
            subscription.change_plan(self.enterprise_plan_version)
        else:
            try:
                self.make_new_enterprise_subscription(domain)
            except NewSubscriptionError as e:
                print e.message
                return
        print 'Domain %s has been upgraded to enterprise level.' % domain.name

    def make_new_enterprise_subscription(self, domain):
        account, _ = BillingAccount.get_or_create_account_by_domain(
            domain.name,
            account_type=BillingAccountType.CONTRACT,
            created_by="management command",
        )
        Subscription.new_domain_subscription(
            account,
            domain.name,
            self.enterprise_plan_version,
        )

    @property
    def enterprise_plan_version(self):
        return SoftwarePlanVersion.objects.filter(
            plan__edition=SoftwarePlanEdition.ENTERPRISE
        )[0]
