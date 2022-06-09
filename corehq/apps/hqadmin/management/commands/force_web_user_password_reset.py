
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.urls import reverse

from corehq.apps.hqadmin.utils import unset_password
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser
from corehq.util.argparse_types import utc_timestamp
from dimagi.utils.web import get_url_base


class Command(BaseCommand):
    """
    For each user in newline-separated `web_users_file`, log the user out and force them to reset their password.
    It also sends them an email with some context and a link to where they can initiate the password reset.

    Usage:
        $ ./manage.py force_web_user_password_reset web_users_file
    """

    def add_arguments(self, parser):
        parser.add_argument('web_users_file')
        parser.add_argument('--skip-if-reset-since', type=utc_timestamp,
                            help="Timestamp of the last_password_set after which we will not force a reset."
                                 " Format as YYYY-MM-DD HH:MM:SS")

    def handle(self, web_users_file, skip_if_reset_since, **options):
        web_user_usernames = get_lines_from_file(web_users_file)
        errors = []
        web_users_to_reset = []
        web_users_to_skip_due_to_recent_reset = []
        for web_user_username in web_user_usernames:
            web_user = WebUser.get_by_username(web_user_username)
            if web_user is None:
                errors.append(f'No user named {web_user_username}')
            elif not web_user.is_web_user():
                errors.append(f'{web_user_username} is not a WebUser')
            elif skip_if_reset_since and web_user.last_password_set \
                    and web_user.last_password_set > skip_if_reset_since:
                web_users_to_skip_due_to_recent_reset.append(web_user)
            else:
                web_users_to_reset.append(web_user)

        if errors:
            errors_string = '\n'.join(f'  - {error}' for error in errors)
            raise CommandError(f'The following errors were found in your input file:\n{errors_string}')

        if web_users_to_skip_due_to_recent_reset:
            self.stdout.write(f"The following users will be skipped "
                              f"because they have reset their passwords since {skip_if_reset_since}")

            for web_user in web_users_to_skip_due_to_recent_reset:
                self.stdout.write(f"  - {web_user.username} (password last set on {web_user.last_password_set})")

        if not web_users_to_reset:
            print("No web users to reset passwords for. No action taken.")
            return

        self.stdout.write("The following users will be logged out and have their passwords force reset.")
        self.stdout.write("Additionally, they will receive an email directing them to reset their password.")
        for web_user in web_users_to_reset:
            self.stdout.write(f"  - {web_user.username}")

        if 'y' != input('Do you want to proceed? [y/N]'):
            raise CommandError('You have aborted the command and no action was taken.')

        for web_user in web_users_to_reset:
            self.stdout.write(f"Force resetting password for {web_user.username}", ending='')
            force_password_reset(web_user)
            self.stdout.write(" - Done")


def get_lines_from_file(filename):
    with open(filename) as f:
        return [line.strip() for line in f.readlines()]


def force_password_reset(web_user):
    user = web_user.get_django_user()
    unset_password(user)
    user.save()
    url = f"{get_url_base()}{reverse('password_reset_email')}"
    send_html_email_async.delay(
        'Reset Password on CommCare HQ',
        web_user.get_email(),
        (f'Your system administrator has forced a password reset. '
         f'Before you will be able to continue to use CommCare, '
         f'you must reset your password by navigating to {url} and following the instructions.'),
        email_from=settings.DEFAULT_FROM_EMAIL
    )
