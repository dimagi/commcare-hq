from django.core.management.base import BaseCommand
from corehq.motech.repeaters.models import RepeatRecord, Repeater


class Command(BaseCommand):
    help = """
    Shows the number of Repeaters and RepeatRecords per domain.
    """

    def _print_summary(self, summary):
        for info in summary:
            domain = info['key'][0]
            count = info['value']
            self.stdout.write(f'{domain}\t{count}')
        self.stdout.write('*' * 230)

    def handle(self, *args, **options):
        repeater_summary = Repeater.get_db().view(
            'repeaters/repeaters',
            group_level=1,
            reduce=True
        ).all()
        self._print_summary(repeater_summary)

        repeat_records_summary = RepeatRecord.get_db().view(
            'repeaters/repeat_records',
            group_level=1,
            reduce=True
        ).all()
        self._print_summary(repeat_records_summary)
