from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from datetime import date

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q

from six.moves import input

from corehq.apps.accounting.models import BillingAccount, SoftwarePlan, SoftwarePlanVersion, Subscription

APRIL_1 = date(2019, 4, 1)
MAY_1 = date(2019, 5, 1)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('account_id')
        parser.add_argument('plan_id')
        parser.add_argument('april_plan_version_id')
        parser.add_argument('post_april_plan_version_id')

    def handle(self, account_id, plan_id, april_plan_version_id, post_april_plan_version_id, **options):
        account = BillingAccount.objects.get(id=account_id)
        plan = SoftwarePlan.objects.get(id=plan_id)
        april_plan_version = SoftwarePlanVersion.objects.get(id=april_plan_version_id)
        post_april_plan_version = SoftwarePlanVersion.objects.get(id=post_april_plan_version_id)

        print('account = %s' % account.name)
        print('plan = %s' % plan.name)
        print('april_plan_version = %s' % april_plan_version)
        print('post_april_plan_version = %s' % post_april_plan_version)
        print('april_subscriptions.count() = ' % self.get_april_subscriptions_queryset(
            account, plan, april_plan_version).count())
        print('post_april_subscriptions.count() = ' % self.get_post_april_subscriptions_queryset(
            account, plan, post_april_plan_version
        ).count())

        confirm = input('Proceed? Y/N\n')
        if confirm != 'Y':
            print('Aborting!')
            return
        print('Proceeding...')

        with transaction.atomic():
            for april_subscription in self.get_april_subscriptions_queryset(account, plan, april_plan_version):
                original_end_date = april_subscription.date_end
                new_end_date = max(APRIL_1, april_subscription.date_start)
                april_subscription.change_plan(
                    april_plan_version, new_end_date, date_end=original_end_date,
                    note='CRS Enterprise April 1 - May 1 2019'
                )

            for post_april_subscription in self.get_post_april_subscriptions_queryset(
                account, plan, post_april_plan_version
            ):
                original_end_date = post_april_subscription.date_end
                new_end_date = max(MAY_1, post_april_subscription.date_start)
                post_april_subscription.change_plan(
                    post_april_plan_version, new_end_date, date_end=original_end_date,
                    note='CRS Enterprise after May 1 2019'
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
    def get_post_april_subscriptions_queryset(account, plan, post_april_plan_version):
        return Command.get_enterprise_subscriptions_queryset(account, plan).filter(
            Q(date_end__isnull=True) | Q(date_end__gt=MAY_1)
        ).exclude(
            plan_version=post_april_plan_version
        )

    @staticmethod
    def get_enterprise_subscriptions_queryset(account, plan):
        return Subscription.visible_objects.filter(
            account=account,
            plan_version__plan=plan,
        )
