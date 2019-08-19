from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import time
from datetime import datetime

from django.core.management.base import BaseCommand
from gevent.pool import Pool

from corehq.apps.change_feed.producer import producer
from pillow_retry.models import PillowError


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('pillow')

    def handle(self, pillow, **options):
        self.pool = Pool(10)
        self.pillow = pillow
        self.count = 0
        self.start = time.time()

        for errors in self.get_next_errors():
            self.pool.spawn(self._process_errors, errors)

    def get_next_errors(self):
        num_retrieved = 1

        while num_retrieved > 0:
            pillow_errors = (
                PillowError.objects
                .filter(pillow=self.pillow)
                .order_by('date_next_attempt')
            )[:1000]

            num_retrieved = len(pillow_errors)
            yield pillow_errors

            while not self.pool.wait_available(timeout=10):
                time.sleep(1)

        while not self.pool.join(timeout=10):
            print('Waiting for tasks to complete')

    def _process_errors(self, errors):
        for error in errors:
            if error.change_object.metadata:
                producer.send_change(
                    error.change_object.metadata.data_source_name,
                    error.change_object.metadata
                )

        self._delete_errors(errors)
        self.count += 1000
        duration = time.time() - self.start
        print('Processed {} in {}s: {} per s'.format(
            self.count, duration, self.count / duration if duration else self.count)
        )
        print(datetime.utcnow())

    def _delete_errors(self, errors):
        doc_ids = [error.doc_id for error in errors]
        PillowError.objects.filter(doc_id__in=doc_ids).delete()
