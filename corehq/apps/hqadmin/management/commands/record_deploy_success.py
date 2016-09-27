import json
from datadog import api as datadog_api
import requests
from django.core.management import call_command
from corehq.apps.hqadmin.management.utils import get_deploy_email_message_body
from django.core.management.base import BaseCommand
from corehq.apps.hqadmin.models import HqDeploy
from datetime import datetime
from optparse import make_option
from django.conf import settings
from pillow_retry.models import PillowError

STYLE_MARKDOWN = 'markdown'
STYLE_SLACK = 'slack'
DASHBOARD_URL = 'https://p.datadoghq.com/sb/5c4af2ac8-1f739e93ef'
INTEGRATION_TEST_URL = 'https://jenkins.dimagi.com/job/integration-tests/'


def integration_tests_link(style, url):
    return make_link(style, 'tests', url)

def diff_link(style, url):
    return make_link(style, 'here', url)


def dashboard_link(style, url):
    return make_link(style, 'dashboard', url)


def make_link(style, label, url):
    if style == STYLE_MARKDOWN:
        return '[{label}]({url})'.format(label=label, url=url)
    elif style == STYLE_SLACK:
        return '<{url}|{label}>'.format(label=label, url=url)


class Command(BaseCommand):
    help = "Creates an HqDeploy document to record a successful deployment."
    args = "[user]"

    option_list = BaseCommand.option_list + (
        make_option('--user', help='User', default=False),
        make_option('--environment', help='Environment {production|staging etc...}', default=settings.SERVER_ENVIRONMENT),
        make_option('--mail_admins', help='Mail Admins', default=False, action='store_true'),
        make_option('--url', help='A link to a URL for the deploy', default=False),
        make_option(
            '--minutes',
            help='The number of minutes it took to deploy',
            type='int',
            default=None,
        ),
    )

    def handle(self, *args, **options):
        compare_url = options.get('url', None)
        minutes = options.get('minutes', None)

        deploy = HqDeploy(
            date=datetime.utcnow(),
            user=options['user'],
            environment=options['environment'],
            diff_url=compare_url
        )
        deploy.save()

        #  reset PillowTop errors in the hope that a fix has been deployed
        rows_updated = PillowError.bulk_reset_attempts(datetime.utcnow())
        if rows_updated:
            print "\n---------------- Pillow Errors Reset ----------------\n" \
                  "{} pillow errors queued for retry\n".format(rows_updated)

        deploy_notification_text = (
            "CommCareHQ has been successfully deployed to *{}* by *{}* in *{}* minutes. ".format(
                options['environment'],
                options['user'],
                minutes or '?',
            )
        )

        if options['environment'] == 'production':
            deploy_notification_text += "Monitor the {dashboard_link}. "

        if settings.MOBILE_INTEGRATION_TEST_TOKEN:
            deploy_notification_text += "Check the integration {integration_tests_link}. "
            requests.get(
                'https://jenkins.dimagi.com/job/integration-tests/build',
                params={'token': settings.MOBILE_INTEGRATION_TEST_TOKEN},
            )

        deploy_notification_text += "Find the diff {diff_link}"

        if hasattr(settings, 'MIA_THE_DEPLOY_BOT_API'):
            link = diff_link(STYLE_SLACK, compare_url)
            if options['environment'] == 'staging':
                channel = '#staging'
            else:
                channel = '#hq-ops'
            requests.post(settings.MIA_THE_DEPLOY_BOT_API, data=json.dumps({
                "username": "Igor the Iguana",
                "channel": channel,
                "text": deploy_notification_text.format(
                    dashboard_link=dashboard_link(STYLE_SLACK, DASHBOARD_URL),
                    diff_link=link,
                    integration_tests_link=integration_tests_link(STYLE_SLACK, INTEGRATION_TEST_URL)
                ),
            }))

        if settings.DATADOG_API_KEY:
            tags = ['environment:{}'.format(options['environment'])]
            link = diff_link(STYLE_MARKDOWN, compare_url)
            datadog_api.Event.create(
                title="Deploy Success",
                text=deploy_notification_text.format(
                    dashboard_link=dashboard_link(STYLE_MARKDOWN, DASHBOARD_URL),
                    diff_link=link,
                    integration_tests_link=integration_tests_link(STYLE_MARKDOWN, INTEGRATION_TEST_URL)
                ),
                tags=tags,
                alert_type="success"
            )

            print "\n=============================================================\n" \
                  "Congratulations! Deploy Complete.\n\n" \
                  "Don't forget to keep an eye on the deploy dashboard to " \
                  "make sure everything is running smoothly.\n\n" \
                  "https://p.datadoghq.com/sb/5c4af2ac8-1f739e93ef" \
                  "\n=============================================================\n"

        if options['mail_admins']:
            message_body = get_deploy_email_message_body(
                environment=options['environment'], user=options['user'],
                compare_url=compare_url)
            call_command('mail_admins', message_body, **{'subject': 'Deploy successful', 'html': True})
