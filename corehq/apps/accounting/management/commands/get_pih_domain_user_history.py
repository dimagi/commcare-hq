import datetime

from dateutil import parser

from django.core.management import BaseCommand

from corehq.apps.accounting.models import DomainUserHistory
from corehq.apps.es import FormES
from corehq.apps.es.users import UserES
from corehq.apps.users.models import Invitation
from dimagi.utils.dates import add_months_to_date

PIH_DOMAINS = [
    'apzu',
    'chw-in-haiti',
    'copenavajo',
    'edpebola',
    'global-training',
    'harper-1',
    'lesotho-mental-health',
    'peru-ses-mh',
    'referencias',
    'zanmi-lasante',
]


class Command(BaseCommand):
    help = "Gets the DomainUserHistory statistics for PIH's domains"

    def add_arguments(self, parser):
        parser.add_argument('start_date')
        parser.add_argument('end_date')

    def handle(self, start_date, end_date, **kwargs):
        start_date = parser.parse(start_date).date()
        end_date = parser.parse(end_date).date()

        self.stdout.write('\nproject\tmonth\tmobile users\tsubmissions\tweb users')
        for domain in PIH_DOMAINS:
            domain_user_histories = DomainUserHistory.objects.filter(
                domain=domain,
                record_date__gte=start_date,
                record_date__lte=end_date
            )
            for history in domain_user_histories:
                current_date = history.record_date
                current_month = datetime.date(current_date.year, current_date.month, 1)
                next_date = add_months_to_date(history.record_date, 1)
                next_month = datetime.date(next_date.year, next_date.month, 1)
                num_submissions = (
                    FormES()
                    .fields(['received_on'])
                    .domain(domain)
                    .submitted(
                        gte=current_month,
                        lt=next_month
                    ).count()
                )
                prev_active = set(
                    doc['base_username'].split('@')[0]
                    for doc in UserES()
                    .domain(domain)
                    .web_users().is_active()
                    .created(gte=start_date, lt=current_month)
                    .run().hits
                )
                created_web_users = set(
                    doc['base_username'].split('@')[0]
                    for doc in UserES().domain(domain)
                    .web_users()
                    .created(gte=current_month, lt=next_month)
                    .run().hits
                )
                accepted_invites = set(
                    email.split('@')[0]
                    for email in Invitation.objects.filter(
                        domain=domain,
                        is_accepted=True,
                        invited_on__gte=current_month, invited_on__lt=next_month
                    ).values_list('email', flat=True)
                )

                num_web_users = len(prev_active.union(created_web_users).union(accepted_invites))
                num_mobile_users = history.num_users
                month = current_month.strftime('%b %Y')

                self.stdout.write(
                    f'{domain}\t{month}\t{num_mobile_users}\t{num_submissions}\t{num_web_users}'
                )
