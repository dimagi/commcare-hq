import itertools
from collections import defaultdict

from django.contrib.auth.models import User
from django.core.management import BaseCommand

from corehq.apps.es import FormES
from corehq.apps.users.dbaccessors import (
    get_all_user_id_username_pairs_by_domain,
)
from corehq.apps.users.models import CommCareUser, CouchUser


class Command(BaseCommand):
    help = """Find and delete duplicate mobile users in a domain"""

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        duplicate_users = get_duplicate_users(domain)

        if not duplicate_users:
            print('No duplicates found')
            return

        print(f'Found {len(duplicate_users)} usernames with duplicates')
        answer = input("Enter action [delete, print, quit]: ")
        if answer != "delete":
            if answer == "print":
                print("Usernames:", ", ".join(u for u in duplicate_users))
            return
        all_user_id = list(itertools.chain.from_iterable(duplicate_users.values()))
        user_ids_with_forms = get_users_with_forms(domain, all_user_id)

        for username, user_ids in duplicate_users.items():
            print(f'Checking {username}')
            users_by_id = {
                user_id: CommCareUser.get_by_user_id(user_id)
                for user_id in user_ids
            }

            users_with_no_forms = sorted(
                [user for user_id, user in users_by_id.items() if user_id not in user_ids_with_forms],
                key=lambda u: u.created_on
            )

            if not users_with_no_forms:
                print(f'\tAll users for {username} have forms. Skipping user IDs {user_ids}')
                break

            with_forms = set(user_ids) & set(user_ids_with_forms)
            for user_id in with_forms:
                print(f'\tUser {username}({user_id}) has data. Not deleting')

            if not with_forms:
                # all users have no data - keep the oldest one
                users_to_delete = users_with_no_forms[1:]
            else:
                users_to_delete = users_with_no_forms
                assert len(users_to_delete) < len(user_ids)

            delete_duplicate_users(list(users_by_id.values()), users_to_delete)


def get_duplicate_users(domain):
    by_username = defaultdict(list)
    for user_id, username in get_all_user_id_username_pairs_by_domain(domain, include_web_users=False):
        by_username[username].append(user_id)

    dupes = {}
    for username, user_ids in by_username.items():
        if len(user_ids) > 1:
            dupes[username] = user_ids
    return dupes


def get_users_with_forms(domain, user_ids):
    users_with_forms = set()
    for user_id in user_ids:
        f = FormES().domain(domain).user_id(user_id).count()
        if f:
            users_with_forms.add(user_id)
    return users_with_forms


def delete_duplicate_users(all_users, duplicates_to_delete):
    all_usernames = {u.username for u in all_users}
    duplicates_usernames = {u.username for u in duplicates_to_delete}
    assert len(all_usernames) == 1
    assert len(all_usernames & duplicates_usernames) == 1

    print(f'Deleting {len(duplicates_to_delete)} users for {all_users[0].username}')

    for user_to_delete in duplicates_to_delete:
        print(f'    Deleting {user_to_delete.user_id}')
        # CommCareUser.delete
        from corehq.apps.ota.utils import delete_demo_restore_for_user
        delete_demo_restore_for_user(user_to_delete)

        # CouchUser.delete
        user_to_delete.clear_quickcache_for_user()
        # skipped self.get_django_user().delete() because two users may share the same django user

        # Document.delete
        super(CouchUser, user_to_delete).delete()

    duplicate_user_ids = {u.user_id for u in duplicates_to_delete}
    live_user_ids_by_django_user = defaultdict(list)
    for user in all_users:
        user_ids = live_user_ids_by_django_user[user.get_django_user().pk]
        if user.user_id not in duplicate_user_ids:
            # only add users that are still 'live'
            user_ids.append(user.user_id)

    django_users_to_delete = [
        pk for pk, live_users in live_user_ids_by_django_user.items()
        if not len(live_users)
    ]
    for django_user_id in django_users_to_delete:
        print(f'Deleting Django user: {django_user_id}')
        User.objects.get(django_user_id).delete()
