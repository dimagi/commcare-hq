# One-off migration, March 2024

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from corehq.apps.users.models import CouchUser
from corehq.util.log import with_progress_bar
from corehq.util.queries import queryset_to_iterator


class Command(BaseCommand):
    help = "Populate SQL user data from couch"

    def handle(self, **options):
        queryset = get_users_without_user_data()
        for user in with_progress_bar(queryset_to_iterator(queryset, User), queryset.count()):
            populate_user_data(user)


def get_users_without_user_data():
    return User.objects.filter(sqluserdata__isnull=True)


def populate_user_data(django_user):
    user = CouchUser.from_django_user(django_user, strict=True)
    if user:
        for domain in user.get_domains():
            user.get_user_data(domain).save()
