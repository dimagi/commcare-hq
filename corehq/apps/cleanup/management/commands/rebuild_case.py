from django.core.management.base import BaseCommand, CommandError
from casexml.apps.case.cleanup import rebuild_case_from_forms


class Command(BaseCommand):
    args = '<id>'
    help = ('Reprocesses a single case, by ID.')

    def handle(self, *args, **options):
        if len(args) == 1:
            case_id = args[0]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        rebuild_case_from_forms(case_id)
