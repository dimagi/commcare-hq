from django.core.management.base import BaseCommand

from corehq.util.models import (
    BouncedEmail,
    PermanentBounceMeta,
    ComplaintBounceMeta,
)


class Command(BaseCommand):
    help = "Check on the bounced status of an email"

    def add_arguments(self, parser):
        parser.add_argument('bounced_email')

    def handle(self, bounced_email, **options):
        bounced_emails = bounced_email.split(',')
        for email in bounced_emails:
            self.unbounce_email(email)

    def unbounce_email(self, bounced_email):
        is_bounced = BouncedEmail.objects.filter(email=bounced_email).exists()

        if not is_bounced:
            self.stdout.write(f'\n{bounced_email} is NOT bouncing. '
                              f'All clear!\n\n')
            return

        confirm = input(
            f"\n\nAre you sure you want remove {bounced_email} "
            f"from the bounced email list?\n(y/n)"
        )

        if confirm.lower() != "y":
            self.stdout.write("\nOk, keeping them bounced!\n")
            return

        complaints_exist = ComplaintBounceMeta.objects.filter(
            bounced_email__email=bounced_email
        ).exists()

        if complaints_exist:
            confirm_complaints = input(
                f"\n\nWhoa! Hold up. {bounced_email} supposedly has complaints "
                f"against us. Are you sure they took action to lift this?"
                f"\n(y/n)"
            )
            if confirm_complaints.lower() != 'y':
                self.stdout.write("\nWhew, ok...we thought so.\n")
                return

        self.stdout.write(f'\nLet {bounced_email} be free!\n')
        PermanentBounceMeta.objects.filter(
            bounced_email__email=bounced_email
        ).all().delete()
        ComplaintBounceMeta.objects.filter(
            bounced_email__email=bounced_email
        ).all().delete()
        BouncedEmail.objects.filter(email=bounced_email).all().delete()
        self.stdout.write('\nDone.\n\n')
