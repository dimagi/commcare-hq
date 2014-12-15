import logging
from optparse import make_option
from couchdbkit import Database, BulkSaveError
from django.core.management.base import LabelCommand, CommandError
import itertools
from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLog
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CouchUser, UserRole
from couchforms.models import XFormInstance
from dimagi.utils.chunked import chunked


CHUNK_SIZE = 100


class Command(LabelCommand):
    help = "Copy all data (users, forms, cases) associated with a single group"
    args = '<sourcedb> <group_id>'
    label = ""
    option_list = LabelCommand.option_list + (
        make_option('--include-user-owned',
            action='store_true', dest='include_user_owned', default=False,
            help="In addition to getting cases owned by the group itself, also get those owned by all users in the group"),
        make_option('--include-sync-logs',
            action='store_true', dest='include_sync_logs', default=False,
            help="Get sync logs for all users in the group"),
        )

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
        include_user_owned = options["include_user_owned"]

        print 'getting group'
        group = Group.wrap(sourcedb.get(group_id))
        group.save(force_update=True)

        print 'getting domain'
        domain = Domain.wrap(
            sourcedb.view('domain/domains', key=group.domain, include_docs=True,
                          reduce=False, limit=1).one()['doc']
        )
        domain.save(force_update=True)

        owners = [group_id]
        if include_user_owned:
            owners.extend(group.users)

        def keys_for_owner(domain, owner_id):
            return [
                [domain, owner_id, False],
                [domain, owner_id, True],
            ]

        def get_case_ids(owners):
            keys = list(itertools.chain(*[keys_for_owner(domain.name, owner_id) for owner_id in owners]))
            results = sourcedb.view(
                'hqcase/by_owner',
                keys=keys,
                reduce=False,
                include_docs=False,
            )
            return [res['id'] for res in results]

        print 'getting case ids'

        case_ids = get_case_ids(owners)
        xform_ids = set()

        print 'copying %s cases' % len(case_ids)

        for i, subset in enumerate(chunked(case_ids, CHUNK_SIZE)):
            print i * CHUNK_SIZE
            cases = [CommCareCase.wrap(case['doc']) for case in sourcedb.all_docs(
                keys=list(subset),
                include_docs=True,
            )]

            for case in cases:
                xform_ids.update(case.xform_ids)

            self.lenient_bulk_save(CommCareCase, cases)

        if include_user_owned:
            # also grab submissions that may not have included any case data
            for user_id in group.users:
                xform_ids.update(res['id'] for res in sourcedb.view(
                    'reports_forms/all_forms',
                    startkey=['submission user', domain.name, user_id],
                    endkey=['submission user', domain.name, user_id, {}],
                    reduce=False
                ))

        print 'copying %s xforms' % len(xform_ids)
        user_ids = set(group.users)

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

        print 'copying %s users' % len(user_ids)

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
            wrapper=wrap_user,
        ).all()

        role_ids = set([])
        for user in filter(lambda u: u is not None, users):
            # if we use bulk save, django user doesn't get sync'd
            if user.get_domain_membership(domain.name).role_id:
                role_ids.add(user.domain_membership.role_id)
            user.save(force_update=True)

        print 'copying %s roles' % len(role_ids)
        for i, subset in enumerate(chunked(role_ids, CHUNK_SIZE)):
            roles = [UserRole.wrap(role['doc']) for role in sourcedb.all_docs(
                keys=list(subset),
                include_docs=True,
            )]
            self.lenient_bulk_save(UserRole, roles)


        if options['include_sync_logs']:
            print 'copying sync logs'
            for user_id in user_ids:
                log_ids = [res['id'] for res in sourcedb.view("phone/sync_logs_by_user",
                    startkey=[user_id, {}],
                    endkey=[user_id],
                    descending=True,
                    reduce=False,
                    include_docs=True
                )]
                print 'user: %s, logs: %s' % (user_id, len(log_ids))
                for i, subset in enumerate(chunked(log_ids, CHUNK_SIZE)):
                    print i * CHUNK_SIZE
                    logs = [SyncLog.wrap(log['doc']) for log in sourcedb.all_docs(
                        keys=list(subset),
                        include_docs=True,
                    )]
                    self.lenient_bulk_save(SyncLog, logs)
