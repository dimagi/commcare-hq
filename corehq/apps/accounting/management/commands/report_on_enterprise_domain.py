from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from django.core.management import BaseCommand
from django.urls import reverse

from corehq.apps.accounting.models import DefaultProductPlan, Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors.all_commcare_users import get_mobile_user_count
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
        headers = ['Project Space Name', 'Project Space URL', 'Project Space Plan', '# of mobile workers']
        print(','.join(headers))
        for domain in [domain for domain in map(Domain.get_by_name, domain_names) if domain]:
            subscription = Subscription.get_active_subscription_by_domain(domain)
            plan_version = subscription.plan_version if subscription else DefaultProductPlan.get_default_plan_version()

            print(','.join([
                domain.name,
                reverse('domain_login', kwargs={'domain': domain}),     # TODO: make full URL
                plan_version.plan.name,
                str(get_mobile_user_count(domain.name, include_inactive=False)),
            ]))
