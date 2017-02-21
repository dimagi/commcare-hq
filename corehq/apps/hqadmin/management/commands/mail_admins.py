import sys
import json
import requests
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import mail_admins


class Command(BaseCommand):
    help = 'Send args as a one-shot email to the admins.'

    def add_arguments(self, parser):
        parser.add_argument(
            'message',
            nargs='*',
        )
        parser.add_argument('--subject', help='Subject', default='Mail from the console'),
        parser.add_argument('--stdin', action='store_true', default=False, help='Read message body from stdin'),
        parser.add_argument('--html', action='store_true', default=False, help='HTML payload'),
        parser.add_argument('--slack', action='store_true', default=False, help='Whether to send subject to slack'),
        parser.add_argument('--environment', default='', help='The environment we are mailing about'),

    def handle(self, message, **options):
        if options['stdin']:
            message = sys.stdin.read()
        else:
            message = ' '.join(message)

        html = None
        if options['html']:
            html = message

        mail_admins(options['subject'], message, html_message=html)

        if options['slack'] and hasattr(settings, 'MIA_THE_DEPLOY_BOT_API'):
            if options.get('environment') == 'staging':
                channel = '#staging'
            else:
                channel = '#hq-ops'
            requests.post(settings.MIA_THE_DEPLOY_BOT_API, data=json.dumps({
                "channel": channel,
                "username": "Igor the Iguana",
                "text": options['subject'],
            }))
