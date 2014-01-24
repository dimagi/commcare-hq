# Use modern Python
from __future__ import absolute_import, print_function, unicode_literals

# Standard library imports
import logging
from optparse import make_option

# Django imports
import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import LabelCommand, CommandError
from corehq.apps.accounting.models import SoftwarePlan, BillingAccount, Subscription, Subscriber, SoftwarePlanVisibility, SoftwarePlanEdition

logger = logging.getLogger(__name__)


class Command(LabelCommand):
    help = ('Immediately subscribes a domain to a plan and activates that subscription. '
            'Intended for initial testing purposes.')
    args = "<domain> <plan name> <creator>"

    option_list = LabelCommand.option_list + (
        make_option('--list-plans', action='store_true',  default=False,
                    help='List plans that can be subscribed to'),
    )

    def handle(self, *args, **options):
        if 'list-plans' in options:
            subscribable_plans = SoftwarePlan.objects.filter(
                visibility=SoftwarePlanVisibility.PUBLIC
            ).exclude(edition=SoftwarePlanEdition.COMMUNITY)
            for plan in subscribable_plans:
                print(plan.name)
            return
        if len(args) < 2:
            raise CommandError("You must specify <domain> <plan name> <creator>")
        domain = args[0]
        plan_name = args[1]
        try:
            plan_version = SoftwarePlan.get_latest_version(name=plan_name)
        except ObjectDoesNotExist:
            raise CommandError("Plan '%s' does not exist. Did you run cchq_software_plan_bootstrap?" % plan_name)

        logging.info("Subscribing '%s' to the Plan '%s'" % (domain, plan_name))

        account, is_new = BillingAccount.get_or_create_account_by_domain(
            domain, created_by=args[2] if len(args) > 2 else None
        )
        if is_new:
            logging.info("Created new billing account.")
        else:
            logging.info("Using existing billing account.")

        subscriber, _ = Subscriber.objects.get_or_create(domain=domain, organization=None)
        subscription = Subscription(
            account=account,
            plan=plan_version,
            subscriber=subscriber,
            date_start=datetime.date.today(),
            is_active=True,
        )
        subscription.save()
        logging.info("Subscription successfully created.")
