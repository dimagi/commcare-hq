from django.core.management.base import BaseCommand

from corehq.util.models import (
    BouncedEmail,
    PermanentBounceMeta,
    ComplaintBounceMeta,
    TransientBounceEmail,
    BOUNCE_EVENT_THRESHOLD,
    HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE,
)


class Command(BaseCommand):
    help = "Check on the bounced status of an email"

    def add_arguments(self, parser):
        parser.add_argument('bounced_email', help="""
            Emails to check
            - To check multiple emails, separate with a ','
            - To search for all emails containing a substring, use '%searchstring%' syntax
        """)
        parser.add_argument(
            '--show-details',
            action='store_true',
            default=False,
            help='Show extra details of bounced messages',
        )

    def handle(self, bounced_email, **options):
        if bounced_email.startswith('%') and bounced_email.endswith('%'):
            search_string = bounced_email.strip('%')
            assert search_string, f"Search string cannot be empty: {bounced_email}"
            bounced_emails = (
                BouncedEmail.objects.filter(email__contains=search_string)
                .values_list('email', flat=True)
            )
            if bounced_emails:
                print(f'Found bounced emails: {",".join(bounced_emails)}')
            else:
                print('No matching bounced emails found')
        else:
            bounced_emails = bounced_email.split(',')

        for email in bounced_emails:
            self.check_bounced_email(email, show_details=options['show_details'])
            self.stdout.write('*' * 230)

    def check_bounced_email(self, email_string, show_details):
        is_actively_blocked = (
            len(BouncedEmail.get_hard_bounced_emails([email_string])) > 0
        )
        if not is_actively_blocked:
            self.stdout.write(f'{email_string} is NOT blocked. '
                              f'All clear!')
            return
        else:
            self.stdout.write(
                f'{email_string} is blocked! \n'
                f'Please note that we block emails due to the following reasons:\n'
                f'\t- a permanent suppressed bounce is present\n'
                f'\t- more than {BOUNCE_EVENT_THRESHOLD} general '
                f'and/or transient bounces have been received\n'
                f'\nnote that transient bounce information expires '
                f'after {HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE} hours\n\n'
            )

        bounce_query = BouncedEmail.objects.filter(email=email_string)
        if bounce_query.exists():
            bounced_email = bounce_query.first()
            permanent_bounces_query = PermanentBounceMeta.objects.filter(
                bounced_email=bounced_email
            ).order_by('-created')
            complaints_query = ComplaintBounceMeta.objects.filter(
                bounced_email=bounced_email
            ).order_by('-created')

            total_permanent = permanent_bounces_query.count()
            total_complaints = complaints_query.count()

            latest_permanent = (
                permanent_bounces_query.first().created.isoformat()
                if permanent_bounces_query.first() else "\t\t\t"
            )
            latest_complaint = (
                complaints_query.first().created.isoformat()
                if complaints_query.first() else "\t\t\t"
            )
        else:
            bounced_email = None
            total_permanent = 0
            total_complaints = 0
            permanent_bounces_query = None
            complaints_query = None
            latest_permanent = None
            latest_complaint = None

        transient_query = TransientBounceEmail.objects.filter(
            email=email_string
        ).order_by('-created')
        total_transient = transient_query.count()

        latest_transient = (
            transient_query.first().created.isoformat()
            if transient_query.first() else "\t\t\t"
        )

        self.stdout.write(
            '\nEmail\t\t'
            '\tNumber Permanent'
            '\tLast Recorded on'
            '\t\tNumber Complaints'
            '\tLast Recorded on'
            '\t\tNumber Transient'
            '\tLast Recorded on'
        )

        self.stdout.write(
            f'{email_string}'
        )

        self.stdout.write(
            f'\t\t\t'
            f'\t{total_permanent}\t\t'
            f'\t{latest_permanent}'
            f'\t{total_complaints}\t\t'
            f'\t{latest_complaint}'
            f'\t{total_transient}\t\t'
            f'\t{latest_transient}'
        )

        if not show_details:
            return

        self.stdout.write('\n\tDETAILS:\n\n')

        if not is_actively_blocked and bounced_email:
            self.stdout.write(
                '\n\tThis email has a bounce record, but it is NOT being '
                'prevented getting HQ emails.'
            )
            self.stdout.write(
                f'\tThe record was created on {bounced_email.created.isoformat()} '
                f'due to a non-SNS bounce that came to commcarehq-bounces@dimagi.com\n'
                f'\tIt is not possible to determine if this bounce was TRANSIENT '
                f'or PERMANENT until an SNS record comes in.\n\n'
            )

        if transient_query.exists():
            self.stdout.write(
                '\t\nTransient Bounce Records:\n\n'
            )
            self.stdout.write(
                '\tCreated\t\t\t'
                '\tSNS Timestamp\t\t'
                '\tHeaders'
            )
            self.stdout.write('\t' + '_' * 200)
            for record in transient_query.all():
                self.stdout.write(
                    f'\t{record.created.isoformat()}'
                    f'\t{record.timestamp}'
                )
                for key, val in record.headers.items():
                    self.stdout.write('\t' * 10 +
                                      f'{key}:\t{val}')
            self.stdout.write('\n\nt')

        if permanent_bounces_query and permanent_bounces_query.exists():
            self.stdout.write(
                '\tPermanent Bounce Records:\n\n'
            )
            self.stdout.write(
                '\tSub-Type'
                '\t\tSNS Timestamp'
                '\t\t\tCreated on HQ'
                '\t\t\tReason'
                '\t\t\tHeaders'
            )
            self.stdout.write('\t' + '_' * 200)
            for record in permanent_bounces_query.all():
                self.stdout.write(
                    f'\t{record.sub_type}'
                    f'\t\t{record.timestamp}'
                    f'\t{record.created}'
                    f'\t{record.reason}'
                )
                for key, val in record.headers.items():
                    self.stdout.write('\t' * 15 +
                                      f'{key}:\t{val}')
                self.stdout.write('\t' * 15 +
                                  f'destination:\t{record.destination}')
            self.stdout.write('\n\n')

        if complaints_query and complaints_query.exists():
            self.stdout.write(
                '\tComplaint Records:'
            )
            self.stdout.write(
                '\tSNS Timestamp'
                '\t\t\tCreated on HQ'
                '\t\t\tFeedback Type'
                '\t\tSub-Type'
                '\tHeaders'
            )
            self.stdout.write('\t' + '_' * 200)
            for record in complaints_query.all():
                self.stdout.write(
                    f'\t{record.timestamp}'
                    f'\t{record.created}'
                )
                self.stdout.write(
                    '\t' * 8 +
                    f'\t{record.feedback_type}'
                )
                self.stdout.write(
                    '\t' * 11 +
                    f'\t{record.sub_type}'
                )
                self.stdout.write(
                    '\t' * 14 +
                    f'destination: {record.destination}'
                )
                for key, val in record.headers.items():
                    self.stdout.write('\t' * 14 +
                                      f'{key}:\t{val}')
            self.stdout.write('\n\n')
