import uuid

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.urls import reverse

from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.users.models import WebUser
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

    def handle(self, web_users_file, **options):
        web_user_usernames = get_lines_from_file(web_users_file)
        errors = []
        web_users = []
        for web_user_username in web_user_usernames:
            web_user = WebUser.get_by_username(web_user_username)
            if web_user is None:
                errors.append(f'No user named {web_user_username}')
            elif not web_user.is_web_user():
                errors.append(f'{web_user_username} is not a WebUser')
            else:
                web_users.append(web_user)

        if errors:
            raise CommandError(f'The following errors were found in your input file:\n{errors}')

        self.stdout.write("The following users will be logged out and have their passwords force reset.")
        self.stdout.write("Additionally, they will receive an email directing them to reset their password.")
        for web_user_username in web_user_usernames:
            self.stdout.write(f"  - {web_user_username}")

        if 'y' != input('Do you want to proceed? [y/N]'):
            raise CommandError('You have aborted the command and no action was taken.')

        django_users = [web_user.get_django_user() for web_user in web_users]

        for user in django_users:
            self.stdout.write(f"Force resetting password for {user.username}", ending='')
            force_password_reset(user)
            self.stdout.write(" - Done")


def get_lines_from_file(filename):
    with open(filename) as f:
        return [line.strip() for line in f.readlines()]


def force_password_reset(user):
    user.set_password(uuid.uuid4().hex)
    user.save()
    url = f"{get_url_base()}{reverse('password_reset_email')}"
    send_html_email_async.delay(
        'Reset Password on CommCare HQ',
        user.get_email(),
        (f'Your system administrator has forced a password reset. '
         f'Before you will be able to continue to use CommCare, '
         f'you must reset your password by navigating to {url} and following the instructions.'),
        email_from=settings.DEFAULT_FROM_EMAIL
    )
