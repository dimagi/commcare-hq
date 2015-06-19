from optparse import make_option
from couchdbkit import Database
from django.core.management.base import LabelCommand, CommandError
from casexml.apps.case.dbaccessors import get_reverse_indices
from casexml.apps.case.models import CommCareCase
from corehq.apps.domainsync.management.commands.copy_utils import copy_postgres_data_for_docs
from corehq.util.couch_helpers import OverrideDB
from couchforms.models import XFormInstance


class Command(LabelCommand):
    help = "Copy a case and all related forms"
    args = '<sourcedb> <case_id> <domain>'
    option_list = LabelCommand.option_list + (
        make_option('--postgres-db',
                    action='store',
                    dest='postgres_db',
                    default='',
                    help="Name of postgres database to pull additional data from. This should map to a "
                         "key in settings.DATABASES. If not specified no additional postgres data will be "
                         "copied. This is currently used to pull CommCare Supply models."),
    )

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Usage is copy_case, %s' % self.args)

        sourcedb = Database(args[0])
        case_id = args[1]
        doc_ids = [case_id]

        domain = args[2] if len(args) > 2 else None
        def _migrate_case(case_id):
            print 'getting case %s' % case_id
            case = CommCareCase.wrap(sourcedb.get(case_id))
            original_domain = case.domain
            if domain is not None:
                case.domain = domain
            case.save(force_update=True)
            return case, original_domain

        case, orig_domain = _migrate_case(case_id)
        print 'copying %s parent cases' % len(case.indices)
        for index in case.indices:
            _migrate_case(index.referenced_id)
            doc_ids.append(index.referenced_id)

        # hack, set the domain back to make sure we get the reverse indices correctly
        case.domain = orig_domain
        with OverrideDB(CommCareCase, sourcedb):
            child_indices = get_reverse_indices(case)
        print 'copying %s child cases' % len(child_indices)
        for index in child_indices:
            _migrate_case(index.referenced_id)
            doc_ids.append(index.referenced_id)

        print 'copying %s xforms' % len(case.xform_ids)

        def form_wrapper(row):
            doc = row['doc']
            doc.pop('_attachments', None)
            return XFormInstance.wrap(doc)

        xforms = sourcedb.all_docs(
            keys=case.xform_ids,
            include_docs=True,
            wrapper=form_wrapper,
        ).all()
        for form in xforms:
            if domain is not None:
                form.domain = domain
            form.save(force_update=True)
            print 'saved %s' % form._id
            doc_ids.append(form._id)

        if options['postgres_db']:
            copy_postgres_data_for_docs(options['postgres_db'], doc_ids)
