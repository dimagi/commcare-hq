from django.core.management.base import BaseCommand

from corehq.motech.repeaters.models import Repeater

PAYLOAD_INTERVAL = 2  # seconds


class Command(BaseCommand):
    help = 'Sends old forms, cases or other payloads using a repeater'

    def add_arguments(self, parser):
        parser.add_argument('domain', type=str)
        parser.add_argument('repeater_id', type=str)
        # TODO: start_datetime
        # TODO: end_datetime

    def handle(self, *args, **options):
        repeater = get_repeater(options['domain'], options['repeater_id'])
        register_next_payload(repeater, start_datetime=None, end_datetime=None)


def get_repeater(domain, repeater_id):
    repeater = Repeater.get(repeater_id)
    assert repeater.domain == domain
    return repeater


@task
def register_next_payload(repeater, last_payload=None, start_datetime=None, end_datetime=None):
    payload = get_next_payload(repeater, last_payload, start_datetime)
    payload_datetime = get_payload_datetime(payload)
    if payload_datetime > end_datetime:
        return

    repeater.register(payload)
    register_next_payload.async_after(
        PAYLOAD_INTERVAL,
        args=(repeater, payload, payload_datetime, end_datetime)
    )
