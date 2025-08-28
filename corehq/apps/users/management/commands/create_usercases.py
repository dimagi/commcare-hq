from django.core.management.base import BaseCommand

from corehq import privileges
from corehq.apps.app_manager.tasks import create_usercases_for_user_type
from corehq.apps.domain.models import Domain
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Create usercases for all users in the domains with the usercase privilege"

    def add_arguments(self, parser):
        parser.add_argument('domain', nargs='?')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, domain, dry_run, **kwargs):
        all_domains = set([domain]) if domain else set(Domain.get_all_names())

        domains_both_created = 0
        domains_only_web_created = 0

        for d in with_progress_bar(all_domains, length=len(all_domains)):
            if not domain_has_privilege(d, privileges.USERCASE):
                continue

            dom = Domain.get_by_name(d)
            if not dom:
                print(f"Domain {d} does not exist")
                continue

            if dom.usercase_enabled:
                if not dry_run:
                    create_usercases_for_user_type.delay(d, include_web_users=True)

                domains_only_web_created += 1
            else:
                if not dry_run:
                    create_usercases_for_user_type.delay(d, include_commcare_users=True,
                                                include_web_users=True)
                    dom.usercase_enabled = True
                    dom.save()
                domains_both_created += 1

        print(f"Domains with both CommCare and Web users usercases created/synced: {domains_both_created}")
        print(f"Domains with only Web users usercases created/synced: {domains_only_web_created}")
