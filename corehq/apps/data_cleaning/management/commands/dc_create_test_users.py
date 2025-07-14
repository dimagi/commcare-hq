from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.data_cleaning.management.commands.utils import input_validation
from corehq.apps.data_cleaning.management.commands.utils.fake_data_users import (
    DATA_EDITING_TEST_USER_PREFIX,
    get_first_name,
    get_last_name,
)
from corehq.apps.users.dbaccessors import get_all_commcare_users_by_domain
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    help = (
        'Creates fake Mobile Users for a domain who will be using '
        f"the '{input_validation.DATA_EDITING_TEST_APP_NAME}' test app."
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
                f'\n\nDomain {domain} does not have the {input_validation.DATA_EDITING_TEST_APP_NAME} app.'
            )
            self.stdout.write('Please run the dc_create_test_app command first.')
            return

        existing_dc_users = [
            u.username.split('@')[0]
            for u in get_all_commcare_users_by_domain(domain)
            if u.username.startswith(DATA_EDITING_TEST_USER_PREFIX)
        ]
        starting_number = len(existing_dc_users) + 1
        for index in range(starting_number, starting_number + num_users):
            username = f'{DATA_EDITING_TEST_USER_PREFIX}{index}@{domain}.{settings.HQ_ACCOUNT_ROOT}'
            self.stdout.write("\n\n")
            CommCareUser.create(
                domain,
                username,
                user_password,
                None,
                'management command',
                first_name=get_first_name(),
                last_name=get_last_name(),
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f'🆕 Created user {username}'))
        self.stdout.write(self.style.SUCCESS(
            f'\n✅  Created {num_users} users for domain {domain}.'
        ))
