from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime, timedelta
from django.core.management import BaseCommand
from django.core.management.base import CommandError
from django.template.defaultfilters import linebreaksbr
from django.urls import reverse

import io
import re

from dimagi.utils.csv import UnicodeWriter
from dimagi.utils.dates import DateSpan

from corehq.apps.accounting.enterprise import EnterpriseReport
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, Subscription
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.domain.models import Domain
from corehq.apps.es import forms as form_es
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_user_rows,
    get_mobile_user_count,
    get_web_user_count,
)
from corehq.apps.users.models import CommCareUser, CouchUser, WebUser
from six.moves import map


class Command(BaseCommand):
    help = '''
        Generate four CSVs containing details on an enterprise project's domains, web users,
        mobile workers, and recent form submissions.

        Usage:
           report_on_enterprise_domain ACCOUNT_ID USERNAME
    '''

    def add_arguments(self, parser):
        parser.add_argument('account_id')
        parser.add_argument('username')
        parser.add_argument(
            '-m',
            '--message',
            action='store',
            dest='message',
            help='Message to add to email (optional)',
        )
        parser.add_argument(
            '-c',
            '--cc',
            action='store',
            dest='cc',
            help='Comma-separated emails to CC (optional)',
        )

    def _write_file(self, slug):
        report = EnterpriseReport.create(slug, self.couch_user)

        row_count = 0
        csv_file = io.BytesIO()
        writer = UnicodeWriter(csv_file)
        writer.writerow(report.headers)

        for domain in [domain for domain in map(Domain.get_by_name, self.domain_names) if domain]:
            rows = report.rows_for_domain(domain)
            row_count = row_count + len(rows)
            writer.writerows(rows)

        print('Wrote {} lines of {}'.format(row_count, slug))
        attachment = {
            'title': 'enterprise_{}_{}.csv'.format(slug, self.now.strftime('%Y%m%d_%H%M%S')),
            'mimetype': 'text/csv',
            'file_obj': csv_file,
        }
        return (attachment, row_count)

    def handle(self, account_id, username, **kwargs):
        self.couch_user = CouchUser.get_by_username(username)
        self.window = 7

        if not self.couch_user:
            raise CommandError("Option: '--username' must be specified")

        self.now = datetime.utcnow()
        account = BillingAccount.objects.get(id=account_id)
        subscriptions = Subscription.visible_objects.filter(account_id=account.id, is_active=True)
        self.domain_names = set(s.subscriber.domain for s in subscriptions)
        print('Found {} domains for {}'.format(len(self.domain_names), account.name))

        (domain_file, domain_count) = self._write_file(EnterpriseReport.DOMAINS)
        (web_user_file, web_user_count) = self._write_file(EnterpriseReport.WEB_USERS)
        (mobile_user_file, mobile_user_count) = self._write_file(EnterpriseReport.MOBILE_USERS)
        (form_file, form_count) = self._write_file(EnterpriseReport.FORM_SUBMISSIONS)

        message = (
            '''{message}
Report run {timestamp}

Domains: {domain_count}
Web Users: {web_user_count}
Mobile Users: {mobile_user_count}
Forms from past {window} days: {form_count}
            '''.format(**{
                'message': kwargs.get('message') or '',
                'domain_count': domain_count,
                'web_user_count': web_user_count,
                'mobile_user_count': mobile_user_count,
                'window': self.window,
                'form_count': form_count,
                'timestamp': self.now.strftime('%Y-%m-%d %H:%M:%S'),
            })
        )

        cc = []
        if kwargs.get('cc'):
            cc = kwargs.get('cc').split(",")
        send_html_email_async(
            "Report on enterprise account {}".format(account.name), self.couch_user.username,
            linebreaksbr(message), cc=cc, text_content=message, file_attachments=[
                domain_file,
                web_user_file,
                mobile_user_file,
                form_file,
            ]
        )
        print('Emailed {}{}{}'.format(self.couch_user.username, " and " if cc else "", ", ".join(cc)))
