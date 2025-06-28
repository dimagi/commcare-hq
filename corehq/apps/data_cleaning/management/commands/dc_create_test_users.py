from django.core.management.base import BaseCommand

from corehq.apps.data_cleaning.management.commands.utils import input_validation
from corehq.apps.data_cleaning.management.commands.utils.fake_data_users import (
    DATA_CLEANING_TEST_USER_PREFIX,
    get_first_name,
    get_last_name,
)
from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    help = (
        f'Creates fake CommCare users for a domain using '
        f"the '{input_validation.DATA_CLEANING_TEST_APP_NAME}' test app."
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('user_password')
        parser.add_argument('num_users', type=int)

    def handle(self, domain, user_password, num_users, **options):
        is_real_domain = input_validation.is_real_domain(domain)
        if not is_real_domain:
            self.stderr.write(input_validation.get_domain_missing_error(domain))
            return
        existing_app = input_validation.get_fake_app(domain)
        if not existing_app:
            self.stderr.write(
                f'Domain {domain} does not have the {input_validation.DATA_CLEANING_TEST_APP_NAME} app.'
            )
            self.stdout.write('Please run the data_cleaning_add_fake_dappata_app command first.')
            return

        existing_dc_users = [
            u.username.split('@')[0]
            for u in get_all_commcare_users_by_domain(domain)
            if u.username.startswith(DATA_CLEANING_TEST_USER_PREFIX)
        ]
        starting_number = len(existing_dc_users) + 1
        new_dc_users = []
        for index in range(starting_number, starting_number + num_users):
            username = f'{DATA_CLEANING_TEST_USER_PREFIX}{index}@{domain}.commcarehq.org'
            self.stdout.write(f'Creating user {username}...')
            commcare_user = CommCareUser.create(
                domain,
                username,
                user_password,
                None,
                'management command',
                first_name=get_first_name(),
                last_name=get_last_name(),
            )
            commcare_user.is_active = True
            new_dc_users.append(commcare_user)
        CommCareUser.bulk_save(new_dc_users)
        self.stdout.write(f'Created {num_users} users for domain {domain}.')
