import logging
from optparse import make_option
from django.core.management import BaseCommand
import sys
from corehq.apps.accounting.models import Subscriber, Subscription

from dimagi.utils.couch.database import iter_docs
from corehq.apps.domain.models import Domain

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = ('Apply downgrades to all domains, depending on the '
            'currently subscribed plan.')

    option_list = BaseCommand.option_list + (
        make_option('--dry-run', action='store_true',  default=False,
                    help='Do not actually modify the database, '
                         'just verbosely log what happens'),
        make_option('--log-file', action='store_true',  default=False,
                    help='Saves logging output to subscription_changes.txt'),
    )

    def handle(self, dry_run=False, log_file=False, *args, **options):
        if not dry_run:
            confirm_force_reset = raw_input(
                "Are you sure you want to apply downgrades and upgrades to "
                "ALL domains? Type 'yes' to continue. \n"
            )
            if confirm_force_reset != 'yes':
                return

        if log_file:
            orig_stdout = sys.stdout
            f = file('subscription_changes.txt', 'w')
            sys.stdout = f

        all_domain_ids = [d['id'] for d in Domain.get_all(include_docs=False)]
        for domain_doc in iter_docs(Domain.get_db(), all_domain_ids):
            domain = Domain.wrap(domain_doc)
            logging.info("%s START" % domain.name)
            print ("\n")
            plan_version, subscription = Subscription.get_subscribed_plan_by_domain(domain)
            if not subscription:
                subscriber = Subscriber.objects.get_or_create(domain=domain.name)[0]
                print ("Active subscription not found for domain %s"
                       % domain.name)
            else:
                subscriber = subscription.subscriber

            if not dry_run:
                print ("%s => %s" %
                       (domain.name, plan_version.plan.name))
                subscriber.apply_upgrades_and_downgrades(
                    new_plan_version=plan_version,
                    verbose=True,
                )
            else:
                print ("[DRY RUN] %s => %s" %
                       (domain.name, plan_version.plan.name))

            logging.info("%s END" % domain.name)

        if log_file:
            sys.stdout = orig_stdout
            f.close()
