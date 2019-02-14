from __future__ import absolute_import
from __future__ import unicode_literals
from __future__ import print_function

from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from io import open
from six.moves import input


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'user_list_file'
        )
        parser.add_argument(
            'site_code'
        )

    def handle(self, user_list_file, site_code, *args, **kwargs):

        with open(user_list_file) as fin:
            users_to_delete = fin.readlines()
            users_to_delete = [user.strip() for user in users_to_delete]
            choice = input('Total {} users will be deleted: (Y/N)'.format(len(users_to_delete)))
            if not choice.startswith('y'):
                print("Nice!!! Its good to be safe than to be sorry")
                return

            print("Deleting users")
            users_submitted_forms = list()
            for user in users_to_delete:
                user_name = user + '@icds-cas.commcarehq.org'
                mobile_user = CommCareUser.get_by_username(user_name)
                if not mobile_user:
                    continue
                if not mobile_user.reporting_metadata.last_submission_for_user.submission_date and\
                        not mobile_user.reporting_metadata.last_sync_for_user.sync_date:
                    mobile_user.retire()
                else:
                    users_submitted_forms.append(mobile_user)

            print("users submitted forms:")
            print('\n'.join([user.username for user in users_submitted_forms]))

            print('\n{} users deleted. '
                  'Deleting Location with site_code {}'.format(len(users_to_delete)-len(users_submitted_forms),
                                                               site_code))

            location_to_delete = SQLLocation.objects.get(domain='icds-cas', site_code=site_code)

            location_to_delete.delete()

            print("Deleted Location as well. Thank you for Using our services")


