from django.core.management.base import BaseCommand, CommandError

from corehq.apps.app_manager.util import is_valid_case_type
from corehq.apps.domain.models import Domain
from corehq.apps.events.models import AttendanceTrackingConfig


class Command(BaseCommand):
    help = 'Sets a custom case type for attendees for Attendance Tracking'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')

    def handle(self, *args, **options):
        domain = valid_domain(options['domain'])
        case_type = valid_case_type(options['case_type'])
        try:
            config = AttendanceTrackingConfig.objects.get(pk=domain)
        except AttendanceTrackingConfig.DoesNotExist:
            config = AttendanceTrackingConfig(domain=domain)
        config.attendee_case_type = case_type
        config.save()
        self.stdout.write(self.style.SUCCESS(
            f'Attendee case type for "{domain}" set to "{case_type}".'
        ))


def valid_domain(domain_name):
    if not Domain.get_by_name(domain_name):
        raise CommandError(f'Invalid domain {domain_name!r}')
    return domain_name


def valid_case_type(case_type):
    if not is_valid_case_type(case_type, None):
        raise CommandError(f'Invalid case type {case_type!r}')
    return case_type
