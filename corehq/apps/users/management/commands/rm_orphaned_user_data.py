from django.core.management.base import BaseCommand

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CouchUser, SQLUserData


class Command(BaseCommand):
    help = "Remove user data for users no longer part of that domain"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--dry-run', action='store_true', default=False)

    def handle(self, domain, dry_run, **kwargs):
        domains = [domain] if domain else Domain.get_all_names()
        for domain in domains:
            remove_orphaned_user_data_for_domain(domain, dry_run=dry_run)


def remove_orphaned_user_data_for_domain(domain, dry_run):
    orphaned_user_ids = []
    for user_id in SQLUserData.objects.filter(domain=domain).values_list('user_id', flat=True).distinct():
        couch_user = CouchUser.get_by_user_id(user_id)
        if not couch_user:
            if not dry_run:
                SQLUserData.objects.filter(domain=domain, user_id=user_id).delete()
            orphaned_user_ids.append(user_id)
            continue
        try:
            dm = couch_user.get_domain_membership(domain)
        except CouchUser.Inconsistent as e:
            print(f"Ran into inconsistent issue with {user_id} in {domain}: {e}")
            continue

        if not dm:
            if not dry_run:
                SQLUserData.objects.filter(domain=domain, user_id=user_id).delete()
            orphaned_user_ids.append(user_id)

    print(f"Deleted user data for the {domain} domain for the following users: \n{orphaned_user_ids}")
