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

    def handle(self, domain, **kwargs):
        all_domains = set([domain]) if domain else set(Domain.get_all_names())

        for d in with_progress_bar(all_domains, length=len(all_domains)):
            if not domain_has_privilege(d, privileges.USERCASE):
                continue

            dom = Domain.get_by_name(d)
            if not dom:
                print(f"Domain {d} does not exist")
                continue

            if dom.usercase_enabled:
                create_usercases_for_user_type.delay(d, include_web_users=True)
            else:
                create_usercases_for_user_type.delay(d, include_commcare_users=True,
                                                include_web_users=False)
