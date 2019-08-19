from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from datetime import datetime

from django.core.management.base import BaseCommand

from pillow_retry.models import PillowError

from corehq.apps.change_feed.producer import producer


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('pillow')

    def handle(self, pillow, **options):
        self.pillow = pillow
        for errors in self.get_next_errors():
            for error in errors:
                if error.change_object.metadata:
                    producer.send_change(
                        error.change_object.metadata.data_source_type,
                        error.change_object.metadata
                    )

    def get_next_errors(self):
        num_retrieved = 1
        count = 0

        while num_retrieved > 0:
            pillow_errors = (
                PillowError.objects
                .filter(pillow=self.pillow)
                .order_by('date_next_attempt')
            )[:1000]

            num_retrieved = len(pillow_errors)
            yield pillow_errors

            print("deleting")
            doc_ids = [error.doc_id for error in pillow_errors]
            PillowError.objects.filter(doc_id__in=doc_ids).delete()
            count += num_retrieved
            print(count)
            print(datetime.utcnow())
