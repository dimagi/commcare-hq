from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from django.urls import reverse

from corehq.apps.accounting.models import DefaultProductPlan, Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_user_rows, get_mobile_user_count
from corehq.apps.users.models import WebUser
from six.moves import map


class Command(BaseCommand):
    help = 'Print out a CSV containing a table of project space plan and number of mobile workers'

    def add_arguments(self, parser):
        parser.add_argument(
            'domain_names',
            metavar='domain',
            nargs='+',
        )

    def handle(self, domain_names, **kwargs):
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
                    user.last_login.strftime('%Y/%m/%d %H:%M:%S'),
                    domain.name,
                    reverse('domain_login', kwargs={'domain': domain.name}),     # TODO: make full URL
                ]))
