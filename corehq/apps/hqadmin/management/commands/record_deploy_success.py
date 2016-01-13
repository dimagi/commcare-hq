import json
from datadog import api as datadog_api
import requests
from django.core.management import call_command
from django.template.loader import render_to_string
from dimagi.utils import gitinfo
from django.core.management.base import BaseCommand
from corehq.apps.hqadmin.models import HqDeploy
from datetime import datetime
from optparse import make_option
from django.conf import settings
from pillow_retry.models import PillowError

STYLE_MARKDOWN = 'markdown'
STYLE_SLACK = 'slack'


def diff_link(style, url):
    if style == STYLE_MARKDOWN:
        return '[here]({})'.format(url)
    elif style == STYLE_SLACK:
        return '<{}|here>'.format(url)


class Command(BaseCommand):
    help = "Creates an HqDeploy document to record a successful deployment."
    args = "[user]"

    option_list = BaseCommand.option_list + (
        make_option('--user', help='User', default=False),
        make_option('--environment', help='Environment {production|staging etc...}', default=settings.SERVER_ENVIRONMENT),
        make_option('--mail_admins', help='Mail Admins', default=False, action='store_true'),
        make_option('--url', help='A link to a URL for the deploy', default=False),
    )
    
    def handle(self, *args, **options):

        root_dir = settings.FILEPATH
        git_snapshot = gitinfo.get_project_snapshot(root_dir, submodules=True)
        git_snapshot['diff_url'] = options.get('url', None)
        deploy = HqDeploy(
            date=datetime.utcnow(),
            user=options['user'],
            environment=options['environment'],
            code_snapshot=git_snapshot,
        )
        deploy.save()

        #  reset PillowTop errors in the hope that a fix has been deployed
        rows_updated = PillowError.bulk_reset_attempts(datetime.utcnow())
        if rows_updated:
            print "\n---------------- Pillow Errors Reset ----------------\n" \
                  "{} pillow errors queued for retry\n".format(rows_updated)

        deploy_notification_text = (
            "CommCareHQ has been successfully deployed to *{}* by *{}*. "
            "Find the diff {{diff_link}}".format(
                options['environment'],
                options['user'],
            )
        )
        if hasattr(settings, 'MIA_THE_DEPLOY_BOT_API'):
            link = diff_link(STYLE_SLACK, git_snapshot['diff_url'])
            requests.post(settings.MIA_THE_DEPLOY_BOT_API, data=json.dumps({
                "username": "Igor the Iguana",
                "text": deploy_notification_text.format(diff_link=link),
            }))

        if settings.DATADOG_API_KEY:
            tags = ['environment:{}'.format(options['environment'])]
            link = diff_link(STYLE_MARKDOWN, git_snapshot['diff_url'])
            datadog_api.Event.create(
                title="Deploy Success",
                text=deploy_notification_text.format(diff_link=link),
                tags=tags
            )

        if options['mail_admins']:
            snapshot_table = render_to_string('hqadmin/partials/project_snapshot.html', dictionary={'snapshot': git_snapshot})
            message = "Deployed by %s, cheers!" % options['user']
            snapshot_body = "<html><head><title>Deploy Snapshot</title></head><body><h2>%s</h2>%s</body></html>" % (message, snapshot_table)

            call_command('mail_admins', snapshot_body, **{'subject': 'Deploy successful', 'html': True})

