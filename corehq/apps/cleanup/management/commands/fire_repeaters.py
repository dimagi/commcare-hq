import sys

from django.core.management.base import BaseCommand

from corehq.motech.repeaters.const import (
    RECORD_FAILURE_STATE,
    RECORD_PENDING_STATE,
)
from corehq.motech.repeaters.models import RepeaterStub, domain_can_forward
from corehq.motech.repeaters.tasks import process_repeater_stub


class Command(BaseCommand):
    help = 'Fire all repeaters in a domain.'

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, **options):
        if not domain_can_forward(domain):
            print('Domain does not have Data Forwarding or Zapier Integration '
                  'enabled.', file=sys.stderr)
            sys.exit(1)
        for repeater_stub in RepeaterStub.objects.filter(
            domain=domain,
            is_paused=False,
            repeat_records__state__in=(RECORD_PENDING_STATE,
                                       RECORD_FAILURE_STATE)
            # Compare filters to RepeaterStubManager.all_ready(). This
            # command will ignore whether RepeaterStub is waiting for a
            # retry interval to pass.
        ):
            process_repeater_stub.delay(repeater_stub)
