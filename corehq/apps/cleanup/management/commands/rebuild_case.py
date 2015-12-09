from django.core.management.base import BaseCommand, CommandError
from casexml.apps.case.cleanup import rebuild_case_from_forms
from corehq.form_processor.models import RebuildWithReason


class Command(BaseCommand):
    args = '<domain> <id> (reason)'
    help = ('Reprocesses a single case, by ID.')

    def handle(self, *args, **options):
        if len(args) >= 2:
            domain = args[0]
            case_id = args[1]
            reason = args[2] if len(args) == 3 else 'Unknown'
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        rebuild_case_from_forms(domain, case_id, RebuildWithReason(reason=reason))
