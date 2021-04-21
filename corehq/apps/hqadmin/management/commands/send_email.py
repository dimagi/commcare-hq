import sys

from django.core.mail import mail_admins, send_mail
from django.core.management import CommandError
from django.core.management.base import BaseCommand

import settings
from corehq.util.log import send_HTML_email


class Command(BaseCommand):
    help = 'Send once off email.'

    def add_arguments(self, parser):
        parser.add_argument(
            'message',
            nargs='*',
        )
        parser.add_argument('--subject'),
        parser.add_argument('--stdin', action='store_true', default=False, help='Read message body from stdin'),
        parser.add_argument('--html', action='store_true', default=False, help='HTML payload'),
        parser.add_argument('--to-admins', action='store_true', default=False,
                            help='Send to the list of configured admin addresses'),
        parser.add_argument('--recipients', default='',
                            help='Comma-separated list of additional recipient emails'),

    def handle(self, message, **options):
        if options['stdin']:
            message = sys.stdin.read()
        else:
            message = ' '.join(message)

        subject = options['subject']
        admins = options['to_admins']
        recipients = options['recipients']
        is_html = options['html']

        if not subject:
            subject = f"[{settings.SERVER_ENVIRONMENT}] Mail from CommCare HQ"

        if not admins and not recipients:
            raise CommandError("One of '--admins' or '--recipients' must be provided")

        if admins:
            mail_admins(subject, message, html_message=message if is_html else None)

        if recipients:
            recipients = recipients.split(',')
            if is_html:
                send_HTML_email(
                    subject=subject, recipient=recipients, html_content=message
                )
            else:
                send_mail(
                    subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list=recipients
                )
