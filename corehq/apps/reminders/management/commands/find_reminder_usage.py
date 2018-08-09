from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
import six
from corehq.apps.domain.models import Domain
from corehq.apps.reminders.models import CaseReminderHandler, REMINDER_TYPE_KEYWORD_INITIATED
from django.core.management.base import BaseCommand
from io import open


class DomainResult(object):

    def __init__(self):
        self.num_active = 0
        self.num_inactive = 0
        self.types_and_counts = defaultdict(lambda: 0)


class Command(BaseCommand):

    def handle(self, **options):
        handlers = CaseReminderHandler.view(
            'reminders/handlers_by_domain_case_type',
            include_docs=True
        ).all()

        result = defaultdict(lambda: DomainResult())

        for handler in handlers:
            if handler.reminder_type != REMINDER_TYPE_KEYWORD_INITIATED:
                if handler.active:
                    result[handler.domain].num_active += 1
                else:
                    result[handler.domain].num_inactive += 1

            result[handler.domain].types_and_counts[handler.reminder_type] += 1

        # Sort by num_active and then domain
        sorted_result = sorted(
            six.iteritems(result),
            key=lambda two_tuple: (two_tuple[1].num_active, two_tuple[0])
        )

        with open('reminder_status.log', 'w', encoding='utf-8') as f:
            for domain, result in sorted_result:
                domain_obj = Domain.get_by_name(domain)
                f.write('{}\t{}\t{}\t{}\t{}\n'.format(
                    domain,
                    result.num_active,
                    result.num_inactive,
                    domain_obj.uses_new_reminders if domain_obj else None,
                    domain_obj.is_snapshot if domain_obj else None,
                ))
                for reminder_type, count in result.types_and_counts.items():
                    f.write('\t{}\t{}\n'.format(reminder_type, count))
