from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import datetime, timedelta
from django.core.management import BaseCommand
from django.core.management.base import CommandError
from django.urls import reverse
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
    help = 'Print out a CSV containing a table of project space plan and number of mobile workers'

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
            help='Username',
        )

    def handle(self, domain_names, **kwargs):
        date_fmt = '%Y/%m/%d %H:%M:%S'
        couch_user = CouchUser.get_by_username(kwargs.get('username'))
        if not couch_user:
            raise CommandError("Option: '--username' must be specified")

        # Report 1: Project Spaces
        headers = ['Project Space Name', 'Project Space URL', 'Project Space Plan', '# of mobile workers']
        print(','.join(headers))
        for domain in [domain for domain in map(Domain.get_by_name, domain_names) if domain]:
            subscription = Subscription.get_active_subscription_by_domain(domain)
            plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()

            print(','.join([
                domain.name,
                reverse('domain_login', kwargs={'domain': domain.name}),     # TODO: make full URL
                plan_version.plan.name,
                str(get_mobile_user_count(domain.name, include_inactive=False)),
            ]))

        # Report 2: Web Users
        headers = ['Name', 'Email Address', 'Role', 'Last login', 'Project Space Name', 'Project Space URL']
        print(','.join(headers))
        for domain in [domain for domain in map(Domain.get_by_name, domain_names) if domain]:
            for user in get_all_user_rows(domain.name, include_web_users=True, include_mobile_users=False, include_inactive=False, include_docs=True):
                user = WebUser.wrap(user['doc'])
                print(','.join([
                    user.full_name,
                    user.username,
                    user.role_label(domain.name),
                    user.last_login.strftime(date_fmt),
                    domain.name,
                    reverse('domain_login', kwargs={'domain': domain.name}),     # TODO: make full URL
                ]))

        # Report 3: Form Submissions
        headers = ['Form Name', 'Submitted', 'App Name', 'Project Space Name', 'Project Space URL',
                   'Mobile User', 'First Name', 'Last Name']
        print(','.join(headers))
        time_filter = form_es.submitted
        datespan = DateSpan(datetime.now() - timedelta(days=7), datetime.utcnow())
        for domain in [domain for domain in map(Domain.get_by_name, domain_names) if domain]:
            apps = get_brief_apps_in_domain(domain.name)
            apps = {a.id: a.name for a in apps}
            users = get_all_user_rows(domain.name, include_web_users=False, include_mobile_users=True,
                                      include_inactive=False, include_docs=True)
            names = {}
            for user in users:
                user = user['doc']
                username = user['username']
                username = re.sub(r'@.*', '', username)
                names[username] = (user['first_name'], user['last_name'])
            users_filter = form_es.user_id(EMWF.user_es_query(domain.name,
                                           ['t__0'],  # All mobile workers
                                           couch_user)
                            .values_list('_id', flat=True))
            query = (form_es.FormES()
                     .domain(domain.name)
                     .filter(time_filter(gte=datespan.startdate,
                                         lt=datespan.enddate_adjusted))
                     .filter(users_filter))
            for hit in query.run().hits:
                username = hit['form']['meta']['username']
                submitted = datetime.strptime(hit['received_on'][:19], '%Y-%m-%dT%H:%M:%S').strftime(date_fmt)
                print(','.join([
                    hit['form']['@name'],
                    submitted,
                    apps[hit['app_id']] if hit['app_id'] in apps else 'App not found',
                    domain.name,
                    reverse('domain_login', kwargs={'domain': domain.name}),     # TODO: make full URL
                    username,
                    names[username][0] if username in names else 'User not found',
                    names[username][1] if username in names else 'User not found',
                ]))
