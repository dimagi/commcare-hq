import json
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

import requests

from corehq.util.metrics import create_metrics_event
from dimagi.utils.parsing import json_format_datetime
from pillow_retry.models import PillowError

from corehq.apps.hqadmin.management.utils import get_deploy_email_message_body
from corehq.apps.hqadmin.models import HqDeploy
from corehq.util.log import send_HTML_email

STYLE_MARKDOWN = 'markdown'
DASHBOARD_URL = 'https://p.datadoghq.com/sb/5c4af2ac8-1f739e93ef'
INTEGRATION_TEST_URL = 'https://jenkins.dimagi.com/job/integration-tests/'


def integration_tests_link(url):
    return make_link('tests', url)


def diff_link(url):
    return make_link('here', url)


def dashboard_link(url):
    return make_link('dashboard', url)


def make_link(label, url):
    return '[{label}]({url})'.format(label=label, url=url)


class Command(BaseCommand):
    help = "Creates an HqDeploy object to record a successful deployment."

    def add_arguments(self, parser):
        parser.add_argument('--user', help='User', default=False)
        parser.add_argument('--environment', help='Environment {production|staging etc...}', default=settings.SERVER_ENVIRONMENT)
        parser.add_argument('--mail_admins', help='Mail Admins', default=False, action='store_true')
        parser.add_argument('--url', help='A link to a URL for the deploy', default=False)
        parser.add_argument(
            '--minutes',
            help='The number of minutes it took to deploy',
            type=int,
            default=None,
        )
        parser.add_argument('--commit', help='Last git commit sha', default=None)

    def handle(self, **options):
        compare_url = options.get('url', None)
        minutes = options.get('minutes', None)

        deploy = HqDeploy(
            date=datetime.utcnow(),
            user=options['user'],
            environment=options['environment'],
            diff_url=compare_url,
            commit=options['commit']
        )
        deploy.save()

        #  reset PillowTop errors in the hope that a fix has been deployed
        rows_updated = PillowError.bulk_reset_attempts(datetime.utcnow())
        if rows_updated:
            print("\n---------------- Pillow Errors Reset ----------------\n" \
                  "{} pillow errors queued for retry\n".format(rows_updated))

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
            requests.get(
                'https://jenkins.dimagi.com/job/integration-tests-pipeline/build',
                params={'token': settings.MOBILE_INTEGRATION_TEST_TOKEN},
            )

        deploy_notification_text += "Find the diff {diff_link}"

        if settings.DATADOG_API_KEY:
            link = diff_link(compare_url)
            create_metrics_event(
                title="Deploy Success",
                text=deploy_notification_text.format(
                    dashboard_link=dashboard_link(DASHBOARD_URL),
                    diff_link=link,
                    integration_tests_link=integration_tests_link(INTEGRATION_TEST_URL)
                ),
                tags={'environment': options['environment']},
                alert_type="success"
            )

            print(
                "\n=============================================================\n"
                "Congratulations! Deploy Complete.\n\n"
                "Don't forget to keep an eye on the deploy dashboard to "
                "make sure everything is running smoothly.\n\n"
                "https://app.datadoghq.com/dashboard/xch-zwt-vzv/hq-deploy-dashboard?tpl_var_environment={}"
                "\n=============================================================\n".format(
                    settings.SERVER_ENVIRONMENT
                )
            )

        if options['mail_admins']:
            message_body = get_deploy_email_message_body(user=options['user'], compare_url=compare_url)
            subject = 'Deploy Successful - {}'.format(options['environment'])
            call_command('mail_admins', message_body, **{'subject': subject, 'html': True})
            if settings.DAILY_DEPLOY_EMAIL:
                recipient = settings.DAILY_DEPLOY_EMAIL

                send_HTML_email(subject=subject,
                                recipient=recipient,
                                html_content=message_body)

        if settings.SENTRY_CONFIGURED and settings.SENTRY_API_KEY:
            create_update_sentry_release()
            notify_sentry_deploy(minutes)


def create_update_sentry_release():
    from settingshelper import get_release_name, get_git_commit
    release = get_release_name(settings.BASE_DIR, settings.SERVER_ENVIRONMENT)
    headers = {'Authorization': 'Bearer {}'.format(settings.SENTRY_API_KEY), }
    payload = {
        'version': release,
        'refs': [{
            'repository': settings.SENTRY_REPOSITORY,
            'commit': get_git_commit(settings.BASE_DIR)
        }],
        'projects': [settings.SENTRY_PROJECT_SLUG]
    }
    releases_url = f'https://sentry.io/api/0/organizations/{settings.SENTRY_ORGANIZATION_SLUG}/releases/'
    response = requests.post(releases_url, headers=headers, json=payload)
    if response.status_code == 208:
        # already created so update
        payload.pop('version')
        requests.put('{}{}/'.format(releases_url, release), headers=headers, json=payload)


def notify_sentry_deploy(duration_mins):
    from settingshelper import get_release_name
    headers = {'Authorization': 'Bearer {}'.format(settings.SENTRY_API_KEY), }
    payload = {
        'environment': settings.SERVER_ENVIRONMENT,
    }
    if duration_mins:
        utcnow = datetime.utcnow()
        payload.update({
            'dateStarted': json_format_datetime(utcnow - timedelta(minutes=duration_mins)),
            'dateFinished': json_format_datetime(utcnow),
        })
    version = get_release_name(settings.BASE_DIR, settings.SERVER_ENVIRONMENT)
    org_slug = settings.SENTRY_ORGANIZATION_SLUG
    releases_url = f'https://sentry.io/api/0/organizations/{org_slug}/releases/{version}/deploys/'
    requests.post(releases_url, headers=headers, json=payload)
