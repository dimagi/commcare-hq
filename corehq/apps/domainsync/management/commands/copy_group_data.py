import logging
from couchdbkit import Database, BulkSaveError, ResourceConflict
from django.core.management.base import LabelCommand, CommandError
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked


class Command(LabelCommand):
    help = "Copy all data (users, forms, cases) associated with a single group"
    args = '<sourcedb> <group_id>'
    label = ""

    def lenient_bulk_save(self, cls, docs):
        try:
            cls.get_db().bulk_save(docs)
        except BulkSaveError as e:
            other = [error for error in e.errors if error['error'] != 'conflict']
            if other:
                logging.exception(other)
                raise

    def handle(self, *args, **options):
        if len(args) != 2:
            raise CommandError('Usage is copy_group_data %s' % self.args)

        sourcedb = Database(args[0])
        group_id = args[1]

        print 'getting group'
        group = Group.wrap(sourcedb.get(group_id))
        group.save(force_update=True)

        print 'getting domain'
        domain = Domain.wrap(
            sourcedb.view('domain/domains', key=group.domain, include_docs=True,
                          reduce=False, limit=1).one()['doc']
        )
        domain.save(force_update=True)

        print 'getting cases'
        cases = sourcedb.view(
            'hqcase/by_owner',
            keys=[
                [group.domain, group_id, False],
                [group.domain, group_id, True],
            ],
            wrapper=lambda row: CommCareCase.wrap(row['doc']),
            reduce=False,
            include_docs=True
        ).all()
        self.lenient_bulk_save(CommCareCase, cases)


        print 'compiling xform_ids'
        xform_ids = set()
        for case in cases:
            xform_ids.update(case.xform_ids)

        print 'getting xforms'
        user_ids = set(group.users)
        CHUNK_SIZE = 100

        def form_wrapper(row):
            doc = row['doc']
            doc.pop('_attachments', None)
            return XFormInstance.wrap(doc)
        for i, subset in enumerate(chunked(xform_ids, CHUNK_SIZE)):
            print i * CHUNK_SIZE
            xforms = sourcedb.all_docs(
                keys=list(subset),
                include_docs=True,
                wrapper=form_wrapper,
            ).all()
            self.lenient_bulk_save(XFormInstance, xforms)

            for xform in xforms:
                user_id = xform.metadata.userID
                user_ids.add(user_id)

        print 'getting users'

        def wrap_user(row):
            try:
                doc = row['doc']
            except KeyError:
                logging.exception('trouble with user result %r' % row)
                return None

            try:
                return CouchUser.wrap_correctly(doc)
            except Exception:
                logging.exception('trouble with user %s' % doc['_id'])
                return None

        users = sourcedb.all_docs(
            keys=list(user_ids),
            include_docs=True,
            wrapper=wrap_user
        ).all()
        for user in users:
            # if we use bulk save, django user doesn't get sync'd
            user.save(force_update=True)
