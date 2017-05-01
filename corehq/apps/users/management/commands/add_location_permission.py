from __future__ import print_function
from django.core.management.base import BaseCommand
from dimagi.utils.decorators.memoized import memoized
from corehq.apps.users.models import UserRole
from corehq.dbaccessors.couchapps.all_docs import get_doc_ids_by_class
from corehq.util.couch import iter_update, DocUpdate
from corehq.util.log import with_progress_bar


class Command(BaseCommand):
    help = "Migrate UserRoles, using whatever edit_commcare_users is set to for edit_locations"

    def add_arguments(self, parser):
        parser.add_argument(
            '--noinput',
            action='store_true',
            default=False,
        )

    def handle(self, **options):
        if not options['noinput']:
            num_roles = len(get_all_role_ids())
            confirm = raw_input("Found {} roles, update? (Y/n)\n".format(num_roles))
            if confirm == 'n':
                print("Aborting.")
                return
        update_all_roles()


@memoized
def get_all_role_ids():
    return get_doc_ids_by_class(UserRole)


def update_all_roles():
    all_role_ids = get_doc_ids_by_class(UserRole)
    iter_update(UserRole.get_db(), update_role, with_progress_bar(all_role_ids), verbose=True)


def update_role(role_doc):
    role = UserRole.wrap(role_doc)
    # Currently we just use `edit_commcare_users` for both, so for existing
    # roles, let's default to that behavior
    role.permissions.edit_locations = role.permissions.edit_commcare_users
    return DocUpdate(role.to_json())
