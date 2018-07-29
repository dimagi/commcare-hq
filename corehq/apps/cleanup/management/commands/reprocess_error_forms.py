from __future__ import print_function

from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from django.core.management.base import BaseCommand

from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors
from corehq.form_processor.utils import should_use_sql_backend
from corehq.form_processor.reprocess import reprocess_xform_error
from corehq.util.log import with_progress_bar
from couchforms.dbaccessors import get_form_ids_by_type


class Command(BaseCommand):
    help = ('Reprocesses all documents tagged as errors and tries to '
            'regenerate the appropriate case blocks for them. Can pass in '
            'a domain and date to process forms received after that date or '
            'just a domain to process all problem forms in the domain.')

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--verbose',
            action='store_true',
            dest='verbose',
            default=False,
        )
        parser.add_argument(
            '--dryrun',
            action='store_true',
            dest='dryrun',
            default=False,
            help="Don't do the actual reprocessing, just print the ids that would be affected",
        )

    def handle(self, domain, **options):
        verbose = options["verbose"] or options["dryrun"]

        succeeded = []
        failed = []
        error_messages = defaultdict(lambda: 0)
        problem_ids = self._get_form_ids(domain)
        prefix = "Processing: "
        form_iterator = FormAccessors(domain).iter_forms(problem_ids)
        if not verbose:
            form_iterator = with_progress_bar(form_iterator, len(problem_ids), prefix=prefix, oneline=False)
        for form in form_iterator:
            if verbose:
                print("%s\t%s\t%s\t%s" % (form.form_id, form.received_on, form.xmlns, form.problem.strip()))

            if not options["dryrun"]:
                try:
                    reprocess_xform_error(form)
                except Exception as e:
                    raise
                    failed.append(form.form_id)
                    error_messages[str(e)] += 1
                else:
                    succeeded.append(form.form_id)

        if not options["dryrun"]:
            print("%s / %s forms successfully processed, %s failures" %
                  (len(succeeded), len(succeeded) + len(failed), len(failed)))
            if error_messages:
                print("The following errors were seen: \n%s" %
                      ("\n".join("%s: %s" % (v, k) for k, v in error_messages.items())))

    def _get_form_ids(self, domain):
        if should_use_sql_backend(domain):
            problem_ids = FormAccessorSQL.get_form_ids_in_domain_by_type(domain, 'XFormError')
        else:
            problem_ids = get_form_ids_by_type(domain, 'XFormError')
        return problem_ids
