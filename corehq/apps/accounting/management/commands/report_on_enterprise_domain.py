from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime, timedelta
from django.core.management import BaseCommand
from django.core.management.base import CommandError
from django.urls import reverse

import csv
import os.path
import re

from dimagi.utils.dates import DateSpan

from corehq.apps.accounting.models import DefaultProductPlan, Subscription
from corehq.apps.app_manager.dbaccessors import get_brief_apps_in_domain
from corehq.apps.domain.models import Domain
from corehq.apps.es import forms as form_es
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_rows, get_mobile_user_count
from corehq.apps.users.models import CouchUser, WebUser
from six.moves import map


class Command(BaseCommand):
    help = '''
        Generate three CSVs containing details on an enterprise project's domains, web users, and recent
        form submissions, respectively.
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_names',
            metavar='domain',
            nargs='+',
        )
        parser.add_argument(
            '-u',
            '--username',
            action='store',
            dest='username',
            help='Username (required)',
        )

    def _domain_url(self, domain):
        return "https://www.commcarehq.org" + reverse('dashboard_domain', kwargs={'domain': domain})

    def _write_file(self, slug, headers, process_domain, multiple=False):
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = 'enterprise_{}_{}.csv'.format(slug, timestamp)
        with open(filename, 'wb') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(headers)
            row_count = 0
            for domain in [domain.name for domain in map(Domain.get_by_name, self.domain_names) if domain]:
                result = process_domain(domain)
                rows = result if multiple else [result]
                row_count = row_count + len(rows)
                for row in rows:
                    csvwriter.writerow(row)
            print('Wrote {} rows of data to {}'.format(row_count, filename))

    def _domain_row(self, domain):
        subscription = Subscription.get_active_subscription_by_domain(domain)
        plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()
        return [
            domain,
            self._domain_url(domain),
            plan_version.plan.name,
            str(get_mobile_user_count(domain, include_inactive=False)),
        ]

    def _web_users_row(self, domain):
        for user in get_all_user_rows(domain, include_web_users=True, include_mobile_users=False, include_inactive=False, include_docs=True):
            user = WebUser.wrap(user['doc'])
            return [
                user.full_name,
                user.username,
                user.role_label(domain),
                user.last_login.strftime(self.date_fmt),
                domain,
                self._domain_url(domain),
            ]

    def _form_submissions_row(self, domain):
        time_filter = form_es.submitted
        datespan = DateSpan(datetime.now() - timedelta(days=700), datetime.utcnow())
        apps = get_brief_apps_in_domain(domain)
        apps = {a.id: a.name for a in apps}
        users = get_all_user_rows(domain, include_web_users=False, include_mobile_users=True,
                                  include_inactive=False, include_docs=True)
        names = {}
        for user in users:
            user = user['doc']
            username = user['username']
            username = re.sub(r'@.*', '', username)
            names[username] = (user['first_name'], user['last_name'])
        users_filter = form_es.user_id(EMWF.user_es_query(domain,
                                       ['t__0'],  # All mobile workers
                                       self.couch_user)
                        .values_list('_id', flat=True))
        query = (form_es.FormES()
                 .domain(domain)
                 .filter(time_filter(gte=datespan.startdate,
                                     lt=datespan.enddate_adjusted))
                 .filter(users_filter))
        rows = []
        for hit in query.run().hits:
            username = hit['form']['meta']['username']
            submitted = datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S').strftime(self.date_fmt)
            rows.append([
                hit['form']['@name'],
                submitted,
                apps[hit['app_id']] if hit['app_id'] in apps else 'App not found',
                domain,
                self._domain_url(domain),
                username,
                names[username][0] if username in names else 'User not found',
                names[username][1] if username in names else 'User not found',
            ])
        return rows

    def handle(self, domain_names, **kwargs):
        self.domain_names = domain_names
        self.date_fmt = '%Y/%m/%d %H:%M:%S'
        self.couch_user = CouchUser.get_by_username(kwargs.get('username'))
        if not self.couch_user:
            raise CommandError("Option: '--username' must be specified")

        print('Processing {} domains'.format(len(self.domain_names)))

        headers = ['Project Space Name', 'Project Space URL', 'Project Space Plan', '# of mobile workers']
        self._write_file('domains', headers, self._domain_row)

        headers = ['Name', 'Email Address', 'Role', 'Last Login', 'Project Space Name', 'Project Space URL']
        self._write_file('web_users', headers, self._web_users_row)

        headers = ['Form Name', 'Submitted', 'App Name', 'Project Space Name', 'Project Space URL',
                   'Mobile User', 'First Name', 'Last Name']
        self._write_file('form_submissions', headers, self._form_submissions_row, multiple=True)
