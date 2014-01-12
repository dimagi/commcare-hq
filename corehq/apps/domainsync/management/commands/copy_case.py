from couchdbkit import Database
from django.core.management.base import LabelCommand, CommandError
from casexml.apps.case.models import CommCareCase
from couchforms.models import XFormInstance


class Command(LabelCommand):
    help = "Copy a case and all related forms"
    args = '<sourcedb> <case_id> <domain>'

    def handle(self, *args, **options):
        if len(args) < 2:
            raise CommandError('Usage is copy_case, %s' % self.args)

        sourcedb = Database(args[0])
        case_id = args[1]
        domain = args[2] if len(args) > 2 else None

        print 'getting case'
        case = CommCareCase.wrap(sourcedb.get(case_id))
        if domain is not None:
            case.domain = domain
        case.save(force_update=True)

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
