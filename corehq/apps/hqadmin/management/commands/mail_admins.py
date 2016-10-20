import sys
import json
import requests
from optparse import make_option
from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.mail import mail_admins


class Command(BaseCommand):
    args = '[message]'
    help = 'Send args as a one-shot email to the admins.'

    option_list = BaseCommand.option_list + (
        make_option('--subject', help='Subject', default='Mail from the console'),
        make_option('--stdin', action='store_true', default=False, help='Read message body from stdin'),
        make_option('--html', action='store_true', default=False, help='HTML payload'),
        make_option('--slack', action='store_true', default=False, help='Whether to send subject to slack'),
        make_option('--environment', default='', help='The environment we are mailing about'),
    )

    def handle(self, *args, **options):
        if options['stdin']:
            message = sys.stdin.read()
        else:
            message = ' '.join(args)

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
