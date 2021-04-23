from datetime import datetime
from uuid import uuid4

from django.core.management.base import BaseCommand

from corehq.apps.domain.shortcuts import create_domain
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import (
    FormRepeater,
    RepeatRecord,
    RepeatRecordAttempt,
)
from corehq.util.log import with_progress_bar

# NUM_DOMAINS = 500  # Prod
NUM_DOMAINS = 5
REPEATERS_PER_DOMAIN = 3
# RECORDS_PER_REPEATER = 50_000  # Prod
RECORDS_PER_REPEATER = 250
ATTEMPTS_PER_RECORD = 3


class Command(BaseCommand):
    help = 'Create a ton of repeaters to mimic Prod'

    def handle(self, *args, **options):
        create_sample_repeaters()


def create_sample_repeaters():
    for domain_name in with_progress_bar(get_domain_names(),
                                         length=NUM_DOMAINS):
        create_domain(domain_name)
        connset = ConnectionSettings.objects.create(
            domain=domain_name,
            name='local httpbin',
            url='http://127.0.0.1:10080/anything',
        )
        for i in range(1, REPEATERS_PER_DOMAIN + 1):
            rep = FormRepeater(
                domain=domain_name,
                connection_settings_id=connset.pk,
            )
            rep.save()
            for j in range(1, RECORDS_PER_REPEATER + 1):
                now = datetime.utcnow()
                attempts = third_time_is_the_charm()
                rec = RepeatRecord(
                    domain=domain_name,
                    repeater_id=rep.get_id,
                    repeater_type=rep.__class__.__name__,
                    payload_id=str(uuid4()),
                    registered_on=now,
                    next_check=None,
                    succeeded=True,
                    overall_tries=len(attempts),
                    attempts=attempts,
                )
                rec.save()


def get_domain_names():
    for i in range(1, NUM_DOMAINS + 1):
        yield f'repeaters-{i:03d}'


def third_time_is_the_charm():
    return [
        RepeatRecordAttempt(
            datetime=datetime.utcnow(),
            failure_reason='Boo',
        ),
        RepeatRecordAttempt(
            datetime=datetime.utcnow(),
            failure_reason='Boo',
        ),
        RepeatRecordAttempt(
            datetime=datetime.utcnow(),
            success_response='Yay',
            succeeded=True,
        ),
    ]
