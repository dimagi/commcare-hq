from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import datetime
from django.core.management.base import BaseCommand
from corehq.motech.repeaters.models import RepeatRecord
from dimagi.utils.post import simple_post


class Command(BaseCommand):
    help = 'Fire all repeaters in a domain.'

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        next_year = datetime.datetime.utcnow() + datetime.timedelta(days=365)
        records = RepeatRecord.all(domain=domain, due_before=next_year)
        for record in records:
            record.fire(post_fn=simple_post)
            print('{} {}'.format(record._id, 'successful' if record.succeeded else 'failed'))
