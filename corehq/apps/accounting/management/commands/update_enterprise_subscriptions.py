from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from django.core.management import BaseCommand

from corehq.apps.accounting.models import BillingAccount, SoftwarePlan, SoftwarePlanVersion


class(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('account_id')
        parser.add_argument('plan_id')
        parser.add_argument('new_plan_version_id')

    def handle(self, account_id, plan_id, new_plan_version_id, **options):
        account = BillingAccount.objects.get(id=account_id)
        plan = SoftwarePlan.objects.get(id=plan_id)
        new_plan_version = SoftwarePlanVersion.objects.get(id=new_plan_version_id)

        print('account = %s' % account)
        print('plan = %s' % plan)
        print('new_plan_version = %s' % new_plan_version)
