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
        Generate three CSVs containing details on an enterprise project's domains, web users, and recent
        form submissions, respectively.

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

    def _domain_properties(self, domain):
        return [
            domain.name,
            domain.hr_name,
            "https://www.commcarehq.org" + reverse('dashboard_domain', kwargs={'domain': domain.name})
        ]

    def _write_file(self, slug, headers, process_domain):
        row_count = 0
        csv_file = io.BytesIO()
        writer = UnicodeWriter(csv_file)
        writer.writerow(headers)

        for domain in [domain for domain in map(Domain.get_by_name, self.domain_names) if domain]:
            rows = process_domain(domain)
            row_count = row_count + len(rows)
            writer.writerows(rows)

        print('Wrote {} lines of {}'.format(row_count, slug))
        attachment = {
            'title': 'enterprise_{}_{}.csv'.format(slug, self.now.strftime('%Y%m%d_%H%M%S')),
            'mimetype': 'text/csv',
            'file_obj': csv_file,
        }
        return (attachment, row_count)

    def _domain_rows(self, domain):
        subscription = Subscription.get_active_subscription_by_domain(domain.name)
        plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()
        return [self._domain_properties(domain) + [
            plan_version.plan.name,
            str(get_mobile_user_count(domain.name, include_inactive=False)),
            str(get_web_user_count(domain.name, include_inactive=False)),
        ]]

    def _web_user_rows(self, domain):
        rows = []
        for user in get_all_user_rows(domain.name, include_web_users=True, include_mobile_users=False,
                                      include_inactive=False, include_docs=True):
            user = WebUser.wrap(user['doc'])
            rows.append([
                user.full_name,
                user.username,
                user.role_label(domain.name),
                self._format_date(user.last_login),
            ] + self._domain_properties(domain))
        return rows

    def _mobile_user_rows(self, domain):
        rows = []
        for user in get_all_user_rows(domain.name, include_web_users=False, include_mobile_users=True,
                                      include_inactive=False, include_docs=True):
            user = CommCareUser.wrap(user['doc'])
            rows.append([
                re.sub(r'@.*', '', user.username),
                user.full_name,
                self._format_date(user.last_login),
                self._format_date(user.reporting_metadata.last_submission_for_user.submission_date),
                user.reporting_metadata.last_submission_for_user.commcare_version or '',
            ] + self._domain_properties(domain))
        return rows

    def _form_rows(self, domain):
        time_filter = form_es.submitted
        datespan = DateSpan(datetime.now() - timedelta(days=self.window), datetime.utcnow())
        apps = get_brief_apps_in_domain(domain.name)
        apps = {a.id: a.name for a in apps}

        users_filter = form_es.user_id(EMWF.user_es_query(domain.name,
                                       ['t__0'],  # All mobile workers
                                       self.couch_user)
                        .values_list('_id', flat=True))
        query = (form_es.FormES()
                 .domain(domain.name)
                 .filter(time_filter(gte=datespan.startdate,
                                     lt=datespan.enddate_adjusted))
                 .filter(users_filter))
        rows = []
        for hit in query.run().hits:
            username = hit['form']['meta']['username']
            submitted = self._format_date(datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S'))
            rows.append([
                hit['form']['@name'],
                submitted,
                apps[hit['app_id']] if hit['app_id'] in apps else 'App not found',
                username,
            ] + self._domain_properties(domain))
        return rows

    def _format_date(self, date):
        return date.strftime('%Y/%m/%d %H:%M:%S') if date else ''

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

        domain_headers = ['Project Space Name', 'Project Name', 'Project URL']

        headers = domain_headers + ['Plan', '# of Mobile Users', '# of Web Users']
        (domain_file, domain_count) = self._write_file('domains', headers, self._domain_rows)

        headers = ['Name', 'Email Address', 'Role', 'Last Login'] + domain_headers
        (web_user_file, web_user_count) = self._write_file('web_users', headers, self._web_user_rows)

        headers = ['Username', 'Name', 'Last Login', 'Last Submission', 'CommCare Version'] + domain_headers
        (mobile_user_file, mobile_user_count) = self._write_file('mobile_users', headers, self._mobile_user_rows)

        headers = ['Form Name', 'Submitted', 'App Name', 'Mobile User'] + domain_headers
        (form_file, form_count) = self._write_file('forms', headers, self._form_rows)

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
