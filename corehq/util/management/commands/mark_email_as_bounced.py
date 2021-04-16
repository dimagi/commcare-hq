import datetime

from django.core.management.base import BaseCommand

from corehq.util.models import (
    BouncedEmail,
    PermanentBounceMeta,
    BounceSubType,
)


class Command(BaseCommand):
    help = "Force an email to be marked as Permanently Bounced and blocked " \
           "from receiving any further emails from HQ"

    def add_arguments(self, parser):
        parser.add_argument('bounced_email', help="""
            Emails to mark as bounced
            - To mark multiple emails, separate with a ','
        """)
        parser.add_argument(
            '--show-details',
            action='store_true',
            default=False,
            help='Show extra details of bounced messages',
        )

    def handle(self, bounced_email, **options):
        bounced_emails = bounced_email.split(',')

        for email in bounced_emails:
            self.mark_email_as_bounced(email)

    def mark_email_as_bounced(self, email_string):
        is_actively_blocked = (
            len(BouncedEmail.get_hard_bounced_emails([email_string])) > 0
        )
        if is_actively_blocked:
            self.stdout.write(
                f"{email_string} is already blocked. "
                f"Use check_bounced_email --show-details for more information."
            )
            return

        bounced_email = BouncedEmail.objects.create(email=email_string)
        PermanentBounceMeta.objects.create(
            bounced_email=bounced_email,
            timestamp=datetime.datetime.utcnow(),
            sub_type=BounceSubType.SUPPRESSED,
            reason="Manual suppression from management command."
        )
        self.stdout.write(f"Successfully marked {email_string} as bounced.")
