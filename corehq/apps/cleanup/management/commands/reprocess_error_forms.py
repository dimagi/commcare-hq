from django.core.management.base import BaseCommand, CommandError, LabelCommand
from corehq.apps.cleanup.xforms import iter_problem_forms, reprocess_form_cases
from couchforms.models import XFormError
from optparse import make_option
from dimagi.utils.parsing import string_to_datetime

class Command(BaseCommand):
    args = '<domain> <since>'
    help = ('Reprocesses all documents tagged as errors and tries to '
            'regenerate the appropriate case blocks for them. Can pass in '
            'a domain and date to process forms received after that date or '
            'just a domain to process all problem forms in the domain.')
    option_list = LabelCommand.option_list + \
        (make_option('--dryrun', action='store_true', dest='dryrun', default=False,
            help="Don't do the actual reprocessing, just print the ids that would be affected"),)

    def handle(self, *args, **options):
        domain = since = None
        if len(args) == 1:
            domain = args[0]
        elif len(args) == 2:
            domain = args[0]
            since = string_to_datetime(args[1])
        else:
            raise CommandError('Usage: %s\n%s' % (self.args, self.help))

        for form in iter_problem_forms(domain, since):
            print "%s\t%s\t%s\t%s\t%s" % (form._id, form.received_on,
                              form.xmlns,
                              form.xpath('form/meta/username'),
                              form.problem.strip())
            if not options["dryrun"]:
                reprocess_form_cases(form)

