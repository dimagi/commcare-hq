from django.core.management.base import BaseCommand, CommandError
from casexml.apps.case.cleanup import rebuild_case_from_forms


class Command(BaseCommand):
    args = '<domain> <id>'
    help = ('Reprocesses a single case, by ID.')

    def handle(self, *args, **options):
        if len(args) == 2:
            domain = args[0]
            case_id = args[1]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        rebuild_case_from_forms(domain, case_id)
