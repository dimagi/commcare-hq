from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from datetime import date

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from six.moves import input

from corehq.apps.accounting.models import BillingAccount, SoftwarePlan, SoftwarePlanVersion, Subscription, \
    SubscriptionType
from corehq.util.log import with_progress_bar

APRIL_1 = date(2019, 4, 1)
MAY_1 = date(2019, 5, 1)
JUNE_1 = date(2019, 6, 1)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('account_id')
        parser.add_argument('plan_id')
        parser.add_argument('april_and_may_plan_version_id')

    def handle(self, account_id, plan_id, april_and_may_plan_version_id, **options):
        account = BillingAccount.objects.get(id=account_id)
        plan = SoftwarePlan.objects.get(id=plan_id)
        april_and_may_plan_version = SoftwarePlanVersion.objects.get(id=april_and_may_plan_version_id)

        print('account = %s' % account.name)
        print('plan = %s' % plan.name)
        print('april_plan_version = %s' % april_and_may_plan_version)
        print(self.get_april_subscriptions_queryset(account, plan, april_and_may_plan_version))
        print('april_subscriptions.count() = %s' % self.get_april_subscriptions_queryset(
            account, plan, april_and_may_plan_version).count())
        print(self.get_may_subscriptions_queryset(account, plan, april_and_may_plan_version))
        print('may_subscriptions.count() = %s' % self.get_may_subscriptions_queryset(
            account, plan, april_and_may_plan_version).count())

        confirm = input('Proceed? Y/N\n')
        if confirm != 'Y':
            print('Aborting!')
            return
        print('Proceeding...')

        with transaction.atomic():
            self.get_april_subscriptions_queryset(account, plan, april_and_may_plan_version).update(
                plan_version=april_and_may_plan_version
            )

        with transaction.atomic():
            self.get_may_subscriptions_queryset(account, plan, april_and_may_plan_version).update(
                plan_version=april_and_may_plan_version
            )

    @staticmethod
    def get_april_subscriptions_queryset(account, plan, april_plan_version):
        return Command.get_enterprise_subscriptions_queryset(account, plan).filter(
            Q(date_end__isnull=True) | Q(date_end__gt=APRIL_1),
            date_start__lt=MAY_1,
        ).exclude(
            plan_version=april_plan_version,
        )

    @staticmethod
    def get_may_subscriptions_queryset(account, plan, may_plan_version):
        return Command.get_enterprise_subscriptions_queryset(account, plan).filter(
            Q(date_end__isnull=True) | Q(date_end__gt=MAY_1),
            date_start__lt=JUNE_1,
        ).exclude(
            plan_version=may_plan_version,
        )

    @staticmethod
    def get_enterprise_subscriptions_queryset(account, plan):
        return Subscription.visible_objects.filter(
            account=account,
            plan_version__plan=plan,
        )
