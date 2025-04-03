import logging

from django.core.management.base import BaseCommand

from corehq.apps.ota.utils import reset_demo_user_restore
from corehq.apps.users.dbaccessors import get_practice_mode_mobile_workers
from corehq.apps.users.models import CommCareUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reset restores for demo users in a domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Do not actually reset, just verbosely log what will happen',
        )

    def handle(self, domain, dry_run, **options):
        if not dry_run:
            confirmation = input("Please confirm you want to reset for real?(y)")
            if confirmation != 'y':
                logging.info("Aborting! Thanks for being cautious.")
                exit(0)
        if dry_run:
            logging.info("Proceeding with dry run. No real reset will be done.")
        logging.info('------Starting---------')
        for user_details in get_practice_mode_mobile_workers(domain):
            user_id = user_details['_id']
            username = user_details['username']
            commcare_user = CommCareUser.get_by_user_id(user_id)
            logger.info(f"Resetting restore for demo user {username}")
            if not dry_run:
                reset_demo_user_restore(commcare_user, domain)
            logger.info("Done!")
        logging.info('------Completed--------')
        exit(0)
