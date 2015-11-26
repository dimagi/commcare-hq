import datetime
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.repeaters.models import RepeatRecord
from dimagi.utils.post import simple_post


class Command(BaseCommand):
    args = '<domain>'
    help = 'Fire all repeaters in a domain.'

    def handle(self, *args, **options):
        if len(args) == 1:
            domain = args[0]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        next_year = datetime.datetime.utcnow() + datetime.timedelta(days=365)
        records = RepeatRecord.all(domain=domain, due_before=next_year)
        for record in records:
            record.fire(post_fn=simple_post)
            record.save()
            print '{} {}'.format(record._id, 'successful' if record.succeeded else 'failed')
