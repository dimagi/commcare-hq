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
        parser.add_argument(
            '--process-aws',
            action='store_true',
            default=False,
            help='Process only AWS notifications.',
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
            process_aws = options['process_aws']
            self.stdout.write(
                '\n\nLogging into account for {}\n'.format(settings.RETURN_PATH_EMAIL)
            )
            with BouncedEmailManager(
                delete_processed_messages=delete_messages
            ) as bounced_manager:
                if process_aws:
                    self.stdout.write('\n\nProcessing AWS Notifications\n')
                    bounced_manager.process_aws_notifications()
                else:
                    self.stdout.write('\n\nProcessing Mailer Daemon Emails\n')
                    bounced_manager.process_daemon_messages()

            self.stdout.write('\nDone\n\n')
        except OSError:
            self.stdout.write('Not able to connect at this time\n')
