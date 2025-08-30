import time
from itertools import chain

from django.core.management.base import BaseCommand

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.callcenter.sync_usercase import sync_usercases_ignore_web_flag
from corehq.apps.domain.models import Domain
from corehq.util.log import with_progress_bar
from corehq.apps.users.models import CommCareUser, WebUser


class Command(BaseCommand):
    help = "Create usercases for all users in the domains with the usercase privilege"

    def add_arguments(self, parser):
        parser.add_argument('domain', nargs='?')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, domain, dry_run, **kwargs):
        all_domains = set([domain]) if domain else set(Domain.get_all_names())
        processed_user_counter = 0
        RATE_LIMIT = 5000
        SLEEP_TIME = 60

        def _sync_usercases_with_throttle(users, domain):
            nonlocal processed_user_counter
            for user in users:
                sync_usercases_ignore_web_flag(user, domain)
                processed_user_counter += 1
                if processed_user_counter % RATE_LIMIT == 0:
                    time.sleep(SLEEP_TIME)

        domains_both_created = 0
        domains_only_web_created = 0

        for domain in with_progress_bar(all_domains, length=len(all_domains)):
            if not domain_has_privilege(domain, privileges.USERCASE):
                continue

            domain_obj = Domain.get_by_name(domain)
            if not domain_obj:
                print(f"Domain {domain} does not exist")
                continue

            if domain_obj.usercase_enabled:
                if not dry_run:
                    users = WebUser.by_domain(domain)
                    _sync_usercases_with_throttle(users, domain)
                domains_only_web_created += 1
            else:
                if not dry_run:
                    users = chain(WebUser.by_domain(domain), CommCareUser.by_domain(domain))
                    _sync_usercases_with_throttle(users, domain)
                    domain_obj.usercase_enabled = True
                    domain_obj.save()
                domains_both_created += 1

        print(f"Domains with both CommCare and Web users usercases created/synced: {domains_both_created}")
        print(f"Domains with only Web users usercases created/synced: {domains_only_web_created}")
