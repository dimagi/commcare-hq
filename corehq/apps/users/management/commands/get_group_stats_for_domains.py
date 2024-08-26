from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Subscription
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser


class Command(BaseCommand):
    help = "gets the number of mobile workers and number of groups by domain"

    def handle(self, **options):
        self.stdout.write("Domain\tEdition\tNum MW\tNum Groups")
        for domain in Domain.get_all_names():
            num_users = CommCareUser.total_by_domain(domain)
            subscription = Subscription.get_active_subscription_by_domain(domain)
            edition = subscription.plan_version.plan.edition if subscription else "No Plan"
            doc_type = Group.__name__
            row = Group.view(
                'by_domain_doc_type_date/view',
                startkey=[domain, doc_type],
                endkey=[domain, doc_type, {}],
                reduce=True,
                include_docs=False,
            ).one()
            num_groups = row['value'] if row else 0
            if num_groups > 10:
                self.stdout.write(f"{domain}\t{edition}\t{num_users}\t{num_groups}")
