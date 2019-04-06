from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import re
from corehq.apps.data_interfaces.models import CaseRuleUndoer
from dateutil.parser import parse
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Min
from six.moves import input


class Command(BaseCommand):
    help = "Undoes changes made to cases by case rules"

    def add_arguments(self, parser):
        parser.add_argument('domain')

        parser.add_argument(
            '--rule_id',
            dest='rule_id',
            type=int,
            default=None,
        )

        parser.add_argument(
            '--since',
            dest='since',
            default=None,
        )

    def validate_since(self, since):
        if since:
            if not re.match(r'^\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d$', since):
                raise CommandError("Please enter UTC timestamp for --since in the format: YYYY-MM-DD HH:MM:SS")
            return parse(since)
        else:
            return None

    def print_description(self, domain, rule_id, since, count, undoer):
        if count == 0:
            print("No changes to undo.")
            return

        description = "Undoing case rule updates for domain %s" % domain

        if rule_id is not None:
            description += ", rule_id %s" % rule_id

        if since:
            description += ", for changes since %s" % since
        else:
            min_created_on = undoer.get_submission_queryset().aggregate(Min('created_on'))['created_on__min']
            description += ", for changes since %s" % min_created_on

        print(description)
        print("%s change(s) will be undone" % count)

    def handle(self, *args, **options):
        domain = options['domain']
        rule_id = options['rule_id']
        since = self.validate_since(options['since'])

        undoer = CaseRuleUndoer(domain, rule_id=rule_id, since=since)
        count = undoer.get_submission_queryset().count()

        self.print_description(domain, rule_id, since, count, undoer)
        if count == 0:
            return

        answer = input("Are you sure you want to continue? y/n ")
        if answer.strip() != 'y':
            print("Process aborted.")
            return

        print("Processing...")
        result = undoer.bulk_undo(progress_bar=True)
        print("%s form(s) were considered" % result['processed'])
        print("%s form(s) had to be skipped because they opened a case or had errors" % result['skipped'])
        print("%s form(s) were archived" % result['archived'])
