# One-off migration, March 2024

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.users.dbaccessors import get_user_docs_by_username
from corehq.apps.users.user_data import SQLUserData
from corehq.util.log import with_progress_bar
from corehq.util.queries import queryset_to_iterator


class Command(BaseCommand):
    help = "Populate SQL user data from couch"

    def handle(self, **options):
        queryset = get_users_without_user_data()
        users = with_progress_bar(queryset_to_iterator(queryset, User), queryset.count())
        for chunk in chunked(users, 100):
            users_by_username = {user.username: user for user in chunk}
            for user_doc in get_user_docs_by_username(users_by_username.keys()):
                populate_user_data(user_doc, users_by_username[user_doc['username']])


def get_users_without_user_data():
    return User.objects.filter(sqluserdata__isnull=True)


def populate_user_data(user_doc, django_user):
    domains = user_doc.get('domains', [user_doc.get('domain')])
    for domain in domains:
        raw_user_data = user_doc.get('user_data', {})
        raw_user_data.pop(COMMCARE_PROJECT, None)
        profile_id = raw_user_data.pop(PROFILE_SLUG, None)
        if raw_user_data or profile_id:
            sql_data = SQLUserData.objects.create(
                user_id=user_doc['_id'],
                domain=domain,
                data=raw_user_data,
                django_user=django_user,
                profile_id=profile_id,
            )
