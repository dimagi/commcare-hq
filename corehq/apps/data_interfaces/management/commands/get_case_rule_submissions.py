import csv
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.data_interfaces.models import CaseRuleSubmission
from corehq.util.argparse_types import date_type
from corehq.util.log import with_progress_bar
from corehq.util.queries import queryset_to_iterator


class Command(BaseCommand):
    help = "Output form IDs for forms created by case rules"

    def add_arguments(self, parser):
        parser.add_argument(
            'domains',
            metavar='domain',
            nargs='+',
        )

        parser.add_argument(
            '--rule-id',
            type=int,
            default=None,
            help='Limit output to the rule with this ID only.'
        )

        parser.add_argument(
            '--rule-name',
            default=None,
            help='Limit output to the rule with this name only.'
        )

        parser.add_argument('-a', '--archived', action='store_true', help='Only include archived forms.')
        parser.add_argument('-s', '--startdate', type=date_type, help='Start date, inclusive. Format YYYY-MM-DD')
        parser.add_argument('-e', '--enddate', type=date_type, help='End date, exclusive. Format YYYY-MM-DD')

    def handle(self, *args, **options):
        domains = options['domains']
        rule_id = options['rule_id']
        rule_name = options['rule_name']
        if rule_id and rule_name:
            raise CommandError("Specify either 'rule-id' or 'rule-name' but not both.")

        start = options['startdate']
        end = options['enddate']
        archived = options['archived']

        qs = CaseRuleSubmission.objects.filter(
            domain__in=domains,
        )

        if rule_id:
            qs = qs.filter(rule_id=rule_id)
        if rule_name:
            qs = qs.filter(rule__name=rule_name)
        if archived:
            qs = qs.filter(archived=True)

        if start:
            qs = qs.filter(created_on__gte=start)
        if end:
            qs = qs.filter(created_on__lt=end)

        count = qs.count()

        if count == 0:
            print("No rule submissions match the given criteria")
            return

        filename = f"rule_submissions_{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S',)}.csv"
        print(f"Writing data for {count} submissions to {filename}")
        with open(filename, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["domain", "rule_id", "created_on", "form_id", "archived"])
            iterator = queryset_to_iterator(qs, CaseRuleSubmission, limit=10000)
            for submission in with_progress_bar(iterator, count):
                writer.writerow([
                    submission.domain,
                    submission.rule_id,
                    submission.created_on,
                    submission.form_id,
                    submission.archived
                ])
