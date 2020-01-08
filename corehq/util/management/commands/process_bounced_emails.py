from django.core.management.base import BaseCommand
from django.conf import settings

from corehq.util.bounced_email_manager import BouncedEmailManager


class Command(BaseCommand):
    help = "Manually Process Bounced Emails"

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete-messages',
            action='store_true',
            default=False,
            help='Move processed messages to trash.',
        )

    def _print_processed_emails(self, emails):
        for email in emails:
            self.stdout.write(email)

    def handle(self, **options):
        if not settings.RETURN_PATH_EMAIL:
            self.stdout.write(
                '\n\nPlease specify a RETURN_PATH_EMAIL in settings\n'
            )
            return

        if not settings.RETURN_PATH_EMAIL_PASSWORD:
            self.stdout.write(
                '\n\nPlease specify a RETURN_PATH_EMAIL_PASSWORD for {} '
                'in settings\n'.format(settings.RETURN_PATH_EMAIL)
            )
            return

        try:
            delete_messages = options['delete_messages']
            self.stdout.write(
                '\n\nLogging into account for {}\n'.format(settings.RETURN_PATH_EMAIL)
            )
            bounced_manager = BouncedEmailManager(
                delete_processed_messages=delete_messages
            )

            self.stdout.write('\n\nProcessing Bounces\n')
            self._print_processed_emails(bounced_manager.process_bounces())

            self.stdout.write('\n\nProcessing Complaints\n')
            self._print_processed_emails(bounced_manager.process_complaints())

            self.stdout.write('\nLogging Out\n\n')
            bounced_manager.logout()
        except OSError:
            self.stdout.write('Not able to connect at this time\n')
