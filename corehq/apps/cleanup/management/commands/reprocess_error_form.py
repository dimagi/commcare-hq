from django.core.management.base import BaseCommand, CommandError, LabelCommand
from corehq.apps.cleanup.xforms import reprocess_form_cases
from couchforms.models import XFormError

class Command(BaseCommand):
    args = '<id>'
    help = ('Reprocesses a single form, by ID.')

    def handle(self, *args, **options):
        if len(args) == 1:
            id = args[0]
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        reprocess_form_cases(XFormError.get(id))
