import functools
from uuid import UUID

from couchdbkit import ResourceNotFound
from django.db.models.query_utils import Q

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLog
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.form import process_xform_xml
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import safe_delete
from corehq.util.test_utils import unit_testing_only, run_with_multiple_configs, RunConfig
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, CommCareCaseIndexSQL, CaseAttachmentSQL, \
    CaseTransaction
from django.conf import settings


class FormProcessorTestUtils(object):

    @classmethod
    @unit_testing_only
    def delete_all_cases(cls, domain=None):
        assert CommCareCase.get_db().dbname.endswith('test')
        view_kwargs = {}
        if domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}],
            }

        cls._delete_all(
            CommCareCase.get_db(),
            'cases_by_server_date/by_server_modified_on',
            **view_kwargs
        )

        def _sql_delete(query, domain_filter):
            if domain is not None:
                query.filter(domain_filter)
            query.all().delete()

        _sql_delete(CommCareCaseIndexSQL.objects, Q(case__domain=domain))
        _sql_delete(CaseAttachmentSQL.objects, Q(case__domain=domain))
        _sql_delete(CaseTransaction.objects, Q(case__domain=domain))
        _sql_delete(CommCareCaseSQL.objects, Q(domain=domain))

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls, domain=None, user_id=None):
        view = 'couchforms/all_submissions_by_domain'
        view_kwargs = {}
        if domain and user_id:
            view = 'reports_forms/all_forms'
            view_kwargs = {
                'startkey': ['submission user', domain, user_id],
                'endkey': ['submission user', domain, user_id, {}],

            }
        elif domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}]
            }

        cls._delete_all(
            XFormInstance.get_db(),
            view,
            **view_kwargs
        )
        query = XFormInstanceSQL.objects
        if domain is not None:
            query = query.filter(domain=domain)
        if user_id is not None:
            query = query.filter(user_id=user_id)
        query.all().delete()

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        cls._delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    @unit_testing_only
    def _delete_all(db, viewname, **view_kwargs):
        deleted = set()
        for row in db.view(viewname, reduce=False, **view_kwargs):
            doc_id = row['id']
            if id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass


run_with_all_backends = functools.partial(
    run_with_multiple_configs,
    run_configs=[
        # run with default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            post_run=lambda *args, **kwargs: args[0].tearDown()
        ),
        # run with inverse of default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            pre_run=lambda *args, **kwargs: args[0].setUp(),
        ),
    ]
)


@unit_testing_only
def post_xform(instance_xml, attachments=None, domain='test-domain'):
    """
    create a new xform and releases the lock

    this is a testing entry point only and is not to be used in real code

    """
    result = process_xform_xml(domain, instance_xml, attachments=attachments)
    with result.get_locked_forms() as xforms:
        FormProcessorInterface(domain).save_processed_models(xforms[0], xforms)
        return xforms[0]


class UuidAssertMixin(object):
    def to_uuid_safe(self, id_):
        return id_ if id_ is None or isinstance(id_, UUID) else UUID(id_)

    def assertUuidEqual(self, id1, id2):
        return self.assertEqual(self.to_uuid_safe(id1), self.to_uuid_safe(id2))

    def assertUuidNotEqual(self, id1, id2):
        return self.assertNotEqual(self.to_uuid_safe(id1), self.to_uuid_safe(id2))

    def assertUuidListEqual(self, list1, list2):
        def to_uuids(alist):
            if alist and isinstance(alist[0], UUID):
                return alist

            return [
                UUID(id_) for id_ in alist
            ]
        return self.assertEqual(to_uuids(list1), to_uuids(list2))
