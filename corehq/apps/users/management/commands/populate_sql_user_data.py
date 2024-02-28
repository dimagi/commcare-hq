# One-off migration, March 2024

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from dimagi.utils.chunked import chunked

from corehq.apps.case_search.const import COMMCARE_PROJECT
from corehq.apps.custom_data_fields.models import PROFILE_SLUG
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
    if user_doc['doc_type'] == 'WebUser':
        domains = user_doc['domains']
    else:
        domains = [user_doc['domain']]

    for domain in domains:
        raw_user_data = user_doc.get('user_data', {})
        raw_user_data.pop(COMMCARE_PROJECT, None)
        profile_id = raw_user_data.pop(PROFILE_SLUG, None)
        if raw_user_data or profile_id:
            SQLUserData.objects.create(
                user_id=user_doc['_id'],
                domain=domain,
                data=raw_user_data,
                django_user=django_user,
                profile_id=profile_id,
            )
