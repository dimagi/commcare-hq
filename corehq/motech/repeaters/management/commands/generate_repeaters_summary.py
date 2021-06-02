from django.core.management.base import BaseCommand
from corehq.motech.repeaters.models import RepeatRecord, Repeater


class Command(BaseCommand):
    help = """
    Shows the number of Repeaters and RepeatRecords per domain.
    """

    def handle(self, *args, **options):
        self.stdout.write("\n")
        self.stdout.write('fetching repeater data...')
        repeater_summary = Repeater.get_db().view(
            'repeaters/repeaters',
            group_level=1,
            reduce=True
        ).all()
        repeaters_by_domain = {info['key'][0]: info['value'] for info in repeater_summary}

        self.stdout.write("\n")
        self.stdout.write('fetching repeat record data...')
        repeat_records_summary = RepeatRecord.get_db().view(
            'repeaters/repeat_records',
            group_level=1,
            reduce=True
        ).all()

        self.stdout.write("\n\n\n")
        self.stdout.write("Domain\tRepeaters\tRepeatRecords")
        for info in repeat_records_summary:
            domain = info['key'][0]
            num_repeaters = repeaters_by_domain.get(domain, 0)
            num_repeat_records = info['value']
            self.stdout.write(f'{domain}\t{num_repeaters}\t{num_repeat_records}')
        self.stdout.write('*' * 230)
        self.stdout.write('done...')
