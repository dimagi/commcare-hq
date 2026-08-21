from __future__ import print_function
from __future__ import absolute_import
from bulk_update.helper import bulk_update as bulk_update_helper
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


from corehq.apps.users.models import CommCareUser
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.chunked import chunked
from six.moves import input


class Command(BaseCommand):
    help = """Reset all mobile user passwords to a given password and delete
    personally identifiable data (name, phone_numbers)
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_name',
        )
        parser.add_argument(
            'password',
        )

    def handle(self, domain_name, password, **options):
        url = absolute_reverse('domain_homepage', args=[domain_name])
        confirm = input(
            """
            ## Caution!! ##
            ###############
            You are resetting passwords of all users in {domain} at {url}
            Are you sure want to reset, type your domain name to confirm?
            """.format(domain=domain_name, url=url)
        )
        if not confirm == domain_name:
            print("Aborted")
            return

        all_users = CommCareUser.by_domain(domain_name)
        django_users = User.objects.filter(
            username__endswith="@{domain}.commcarehq.org".format(domain=domain_name)
        )
        assert len(all_users) == django_users.count(), "Something is wrong, django/couch users don't match"

        num_users = len(all_users)
        for i, users in enumerate(chunked(all_users, 1000)):
            for user in users:
                user.phone_numbers = []
                user.first_name = ""
                user.last_name = ""
                user.set_password(password)
            CommCareUser.bulk_save(users)
            print("Updated {count}/{total}".format(count=(i+1)*1000, total=num_users))

        for i, users in enumerate(chunked(django_users, 1000)):
            for user in users:
                user.set_password(password)
                user.first_name = ""
                user.last_name = ""
            bulk_update_helper(users)
            print("Updated {count}/{total}".format(count=(i+1)*1000, total=num_users))
