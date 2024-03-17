import uuid
from contextlib import contextmanager
from datetime import datetime

import attr

from django.conf import settings
from django.db import router
from django.test import TestCase
from django.test.utils import override_settings

from corehq.apps.cleanup.models import DeletedSQLDoc
from corehq.apps.commtrack.const import SUPPLY_POINT_CASE_TYPE
from corehq.form_processor.exceptions import AttachmentNotFound, CaseNotFound, CaseSaveError
from corehq.form_processor.models import (
    CaseAttachment,
    CaseTransaction,
    CommCareCase,
    CommCareCaseIndex,
)
from corehq.form_processor.models.cases import CaseIndexInfo
from corehq.form_processor.tests.utils import (
    FormProcessorTestUtils,
    create_case,
    create_case_with_index,
    sharded,
)
from corehq.sql_db.routers import HINT_PLPROXY
from corehq.sql_db.tests.utils import new_id_in_different_dbalias
from corehq.sql_db.util import get_db_alias_for_partitioned_doc

DOMAIN = 'test-case-accessor'


class BaseCaseManagerTest(TestCase):

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
            FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super(BaseCaseManagerTest, self).tearDown()

    @contextmanager
    def get_case_and_indices(self, mother_id, task_id):
        case = _create_case()
        mother_index = CommCareCaseIndex(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=mother_id,
            relationship_id=CommCareCaseIndex.CHILD
        )
        case.track_create(mother_index)
        task_index = CommCareCaseIndex(
            case=case,
            identifier='task',
            referenced_type='task',
            referenced_id=task_id,
            relationship_id=CommCareCaseIndex.EXTENSION
        )
        case.track_create(task_index)
        case.save(with_tracked_models=True)
        try:
            yield case, mother_index, task_index
        except Exception:
            pass


@sharded
class TestCommCareCaseManager(BaseCaseManagerTest):

    def test_get_case_by_id(self):
        case = _create_case()
        with self.assertNumQueries(1, using=case.db):
            case = CommCareCase.objects.get_case(case.case_id)
        self.assertIsNotNone(case)
        self.assertIsInstance(case, CommCareCase)
        self.assertEqual(DOMAIN, case.domain)
        self.assertEqual('user1', case.owner_id)

    def test_get_case_with_empty_id(self):
        db = get_db_alias_for_partitioned_doc('')
        with self.assertNumQueries(0, using=db), self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case('')

    def test_get_case_with_wrong_domain(self):
        case = _create_case()
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(case.case_id, 'wrong-domain')

    def test_get_case_by_id_missing(self):
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case('missing_case')

    def test_get_cases(self):
        case1 = _create_case()
        case2 = _create_case()

        cases = CommCareCase.objects.get_cases(['missing_case'])
        self.assertEqual(0, len(cases))

        cases = CommCareCase.objects.get_cases([case1.case_id])
        self.assertEqual(1, len(cases))
        self.assertEqual(case1.case_id, cases[0].case_id)

        cases = CommCareCase.objects.get_cases([case1.case_id, case2.case_id], ordered=True)
        self.assertEqual(2, len(cases))
        self.assertEqual(case1.case_id, cases[0].case_id)
        self.assertEqual(case2.case_id, cases[1].case_id)

    def test_iter_cases(self):
        case1 = _create_case()
        case2 = _create_case()
        case_ids = {'missing_case', case1.case_id, case2.case_id, '', None}

        result = CommCareCase.objects.iter_cases(case_ids, DOMAIN)
        self.assertEqual({r.case_id for r in result}, {case1.case_id, case2.case_id})

    def test_get_case_by_external_id(self):
        case1 = _create_case(external_id='123')
        case2 = _create_case(domain='d2', case_type='t1', external_id='123')
        if settings.USE_PARTITIONED_DATABASE:
            self.addCleanup(lambda: FormProcessorTestUtils.delete_all_cases('d2'))

        case = CommCareCase.objects.get_case_by_external_id(DOMAIN, '123')
        self.assertEqual(case.case_id, case1.case_id)

        case = CommCareCase.objects.get_case_by_external_id('d2', '123')
        self.assertEqual(case.case_id, case2.case_id)

        case = CommCareCase.objects.get_case_by_external_id('d2', '123', case_type='t2')
        self.assertIsNone(case)

    def test_get_case_by_external_id_with_multiple_results(self):
        case1_id = uuid.uuid4().hex
        case2_id = new_id_in_different_dbalias(case1_id)  # raises SkipTest on non-sharded db
        _create_case(case_id=case1_id, external_id='123')
        _create_case(case_id=case2_id, external_id='123')

        with self.assertRaises(CommCareCase.MultipleObjectsReturned) as context:
            CommCareCase.objects.get_case_by_external_id(DOMAIN, '123', raise_multiple=True)
        case_ids = {c.case_id for c in context.exception.cases}
        self.assertEqual(case_ids, {case1_id, case2_id})

        # This gets a random case from the set of matching cases.
        # Code exists that uses this feature, but it is not part
        # of a formal specification known to the test author.
        # It may be better/safer to always raise multiple results.
        case = CommCareCase.objects.get_case_by_external_id(DOMAIN, '123')
        self.assertIn(case.case_id, {case1_id, case2_id})

    def test_get_case_ids_that_exist(self):
        case1 = _create_case()
        case2 = _create_case()

        case_ids = CommCareCase.objects.get_case_ids_that_exist(
            DOMAIN,
            ['missing_case', case1.case_id, case2.case_id]
        )
        self.assertItemsEqual(case_ids, [case1.case_id, case2.case_id])

    def test_get_last_modified_dates(self):
        date1 = datetime(1992, 1, 30, 12, 0)
        date2 = datetime(2015, 12, 28, 5, 48)
        case1 = _create_case(server_modified_on=date1)
        case2 = _create_case(server_modified_on=date2)
        _create_case()

        self.assertEqual(
            CommCareCase.objects.get_last_modified_dates(DOMAIN, [case1.case_id, case2.case_id]),
            {case1.case_id: date1, case2.case_id: date2}
        )

    def test_get_case_xform_ids(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)
        form_ids = _create_case_transactions(case)

        self.assertEqual(
            {form_id} | form_ids,
            set(CommCareCase.objects.get_case_xform_ids(case.case_id))
        )

    def test_get_reverse_indexed_cases(self):
        referenced_case_ids = [uuid.uuid4().hex, uuid.uuid4().hex]
        _create_case_with_index(uuid.uuid4().hex, case_is_deleted=True)  # case shouldn't be included in results
        bambi, bambi_ix = _create_case_with_index(referenced_case_ids[0], case_type='bambino')
        child, child_ix = _create_case_with_index(referenced_case_ids[1], case_type='child')
        expected_case_ids = {bambi.case_id, child.case_id}
        expected_indices = {bambi_ix, child_ix}

        cases = CommCareCase.objects.get_reverse_indexed_cases(DOMAIN, referenced_case_ids)
        self.assertEqual({c.case_id for c in cases}, expected_case_ids)
        self.assertEqual({ix for case in cases for ix in case.indices}, expected_indices)

        cases = CommCareCase.objects.get_reverse_indexed_cases(
            DOMAIN, referenced_case_ids, case_types=['child'], is_closed=False)
        self.assertEqual([c.case_id for c in cases], [child.case_id])

        bambi.closed = True
        bambi.save(with_tracked_models=True)
        cases = CommCareCase.objects.get_reverse_indexed_cases(DOMAIN, referenced_case_ids, is_closed=True)
        self.assertEqual([c.case_id for c in cases], [bambi.case_id])

    def test_get_case_by_location(self):
        case = _create_case(case_type=SUPPLY_POINT_CASE_TYPE)
        location_id = uuid.uuid4().hex
        case.location_id = location_id
        case.save(with_tracked_models=True)

        fetched_case = CommCareCase.objects.get_case_by_location(DOMAIN, location_id)
        self.assertEqual(case.id, fetched_case.id)

    def test_get_case_ids_in_domain(self):
        case1 = _create_case(case_type='t1')
        case2 = _create_case(case_type='t1')
        case3 = _create_case(case_type='t2')

        case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN)
        self.assertEqual({case1.case_id, case2.case_id, case3.case_id}, set(case_ids))

        case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN, 't1')
        self.assertEqual({case1.case_id, case2.case_id}, set(case_ids))

        case2.domain = 'new_domain'
        case2.save(with_tracked_models=True)

        case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN)
        self.assertEqual({case1.case_id, case3.case_id}, set(case_ids))

    def test_get_open_case_ids_in_domain_by_type(self):
        case1 = _create_case(user_id="user1", case_type='t1')
        case2 = _create_case(user_id="user1", case_type='t1')
        _create_case(user_id="user1", case_type='t1', closed=True)
        _create_case(user_id="user2", case_type='t1')
        _create_case(user_id="user1", case_type='t2')

        case_ids = CommCareCase.objects.get_open_case_ids_in_domain_by_type(DOMAIN, 't1', ["user1"])
        self.assertEqual(
            set(case_ids),
            {case1.case_id, case2.case_id}
        )

    def test_get_deleted_case_ids_in_domain(self):
        case1 = _create_case()
        case2 = _create_case()
        CommCareCase.objects.soft_delete_cases(DOMAIN, [case1.case_id])

        case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN)
        self.assertEqual(case_ids, [case2.case_id])

        deleted = CommCareCase.objects.get_deleted_case_ids_in_domain(DOMAIN)
        self.assertEqual(deleted, [case1.case_id])

    def test_get_deleted_case_ids_by_owner(self):
        user_id = uuid.uuid4().hex
        case1 = _create_case(user_id=user_id)
        case2 = _create_case(user_id=user_id)
        _create_case(user_id=user_id)

        CommCareCase.objects.soft_delete_cases(DOMAIN, [case1.case_id, case2.case_id])

        case_ids = CommCareCase.objects.get_deleted_case_ids_by_owner(DOMAIN, user_id)
        self.assertEqual(set(case_ids), {case1.case_id, case2.case_id})

    def test_get_case_ids_in_domain_by_owners(self):
        case1 = _create_case(user_id="user1")
        case2 = _create_case(user_id="user1")
        _create_case(user_id="user2")
        case4 = _create_case(user_id="user3")

        case_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(DOMAIN, ["user1", "user3"])
        self.assertEqual(set(case_ids), set([case1.case_id, case2.case_id, case4.case_id]))

    def test_get_case_ids_in_domain_by_owners_closed(self):
        case1 = _create_case(user_id="user1")
        case2 = _create_case(user_id="user1", closed=True)
        case3 = _create_case(user_id="user2")
        case4 = _create_case(user_id="user3", closed=True)

        case_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(
            DOMAIN, ["user1", "user3"], closed=True)
        self.assertEqual(set(case_ids), set([case2.case_id, case4.case_id]))

        case_ids = CommCareCase.objects.get_case_ids_in_domain_by_owners(
            DOMAIN, ["user1", "user2", "user3"], closed=False)
        self.assertEqual(set(case_ids), set([case1.case_id, case3.case_id]))

    def test_save_case_update_index(self):
        case = _create_case()

        original_index = CommCareCaseIndex(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndex.CHILD
        )
        case.track_create(original_index)
        case.save(with_tracked_models=True)

        [index] = CommCareCaseIndex.objects.get_indices(case.domain, case.case_id)
        index.identifier = 'new_identifier'  # shouldn't get saved
        index.referenced_type = 'new_type'
        index.referenced_id = uuid.uuid4().hex
        index.relationship_id = CommCareCaseIndex.EXTENSION
        case.track_update(index)
        case.save(with_tracked_models=True)

        [updated_index] = CommCareCaseIndex.objects.get_indices(case.domain, case.case_id)
        self.assertEqual(updated_index.id, index.id)
        self.assertEqual(updated_index.identifier, original_index.identifier)
        self.assertEqual(updated_index.referenced_type, index.referenced_type)
        self.assertEqual(updated_index.referenced_id, index.referenced_id)
        self.assertEqual(updated_index.relationship_id, index.relationship_id)

    def test_save_case_delete_index(self):
        case = _create_case()

        case.track_create(CommCareCaseIndex(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndex.CHILD
        ))
        case.save(with_tracked_models=True)

        [index] = CommCareCaseIndex.objects.get_indices(case.domain, case.case_id)
        case.track_delete(index)
        case.save(with_tracked_models=True)
        self.assertEqual([], CommCareCaseIndex.objects.get_indices(case.domain, case.case_id))

    def test_save_case_delete_attachment(self):
        case = _create_case()

        case.track_create(CaseAttachment(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml',
            blob_id='127',
            md5='123',
        ))
        case.save(with_tracked_models=True)

        [attachment] = CaseAttachment.objects.get_attachments(case.case_id)
        case.track_delete(attachment)
        case.save(with_tracked_models=True)
        self.assertEqual([], CaseAttachment.objects.get_attachments(case.case_id))

    def test_save_case_update_attachment(self):
        case = _create_case()

        case.track_create(CaseAttachment(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml',
            blob_id='128',
            md5='123',
        ))
        case.save(with_tracked_models=True)

        [attachment] = CaseAttachment.objects.get_attachments(case.case_id)
        attachment.name = 'new_name'

        # hack to call the sql function with an already saved attachment
        case.track_create(attachment)

        with self.assertRaises(CaseSaveError):
            case.save(with_tracked_models=True)

    def test_soft_delete_and_undelete(self):
        _create_case(case_id='c1')
        _create_case(case_id='c2')
        _create_case(case_id='c3')

        # delete
        num = CommCareCase.objects.soft_delete_cases(DOMAIN, ['c1', 'c2'], deletion_id='123')
        self.assertEqual(num, 2)

        for case_id in ['c1', 'c2']:
            case = CommCareCase.objects.get_case(case_id)
            self.assertTrue(case.is_deleted)
            self.assertEqual(case.deletion_id, '123')

        case = CommCareCase.objects.get_case('c3')
        self.assertFalse(case.is_deleted)

        # undelete
        num = CommCareCase.objects.soft_undelete_cases(DOMAIN, ['c2'])
        self.assertEqual(num, 1)

        case = CommCareCase.objects.get_case('c1')
        self.assertTrue(case.is_deleted)
        self.assertEqual(case.deletion_id, '123')

        for case_id in ['c2', 'c3']:
            case = CommCareCase.objects.get_case(case_id)
            self.assertFalse(case.is_deleted, case_id)
            self.assertIsNone(case.deletion_id, case_id)

    def test_hard_delete_cases(self):
        case1 = _create_case()
        case2 = _create_case(domain='other_domain')
        self.addCleanup(lambda: CommCareCase.objects.hard_delete_cases('other_domain', [case2.case_id]))

        case1.track_create(CommCareCaseIndex(
            case=case1,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndex.CHILD
        ))
        case1.track_create(CaseAttachment(
            case=case1,
            attachment_id=uuid.uuid4().hex,
            name='pic.jpg',
            content_type='image/jpeg',
            blob_id='122',
            md5='123',
        ))
        case1.save(with_tracked_models=True)

        num_deleted = CommCareCase.objects.hard_delete_cases(DOMAIN, [case1.case_id, case2.case_id])
        self.assertEqual(1, num_deleted)
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(case1.case_id)

        self.assertEqual([], CommCareCaseIndex.objects.get_indices(case1.domain, case1.case_id))
        self.assertEqual([], CaseAttachment.objects.get_attachments(case1.case_id))
        self.assertEqual([], CaseTransaction.objects.get_transactions(case1.case_id))

    @override_settings(UNIT_TESTING=False)
    def test_bulk_delete_creates_tombstone_if_leave_tombstone_is_true(self):
        cases = [_create_case(deleted_on=datetime.now()) for i in range(3)]
        case_ids = [case.case_id for case in cases]
        CommCareCase.objects.hard_delete_cases(DOMAIN, case_ids, leave_tombstone=True)
        self.assertEqual(DeletedSQLDoc.objects.all().count(), 3)

    @override_settings(UNIT_TESTING=False)
    def test_bulk_delete_raises_error_if_leave_tombstone_is_not_specified(self):
        with self.assertRaises(NotImplementedError):
            CommCareCase.objects.hard_delete_cases(DOMAIN, [])


class TestHardDeleteCasesBeforeCutoff(TestCase):

    def setUp(self):
        self.domain = 'test_hard_delete_cases_before_cutoff'
        self.cutoff = datetime(2020, 1, 1, 12, 30)

    def test_case_is_hard_deleted_if_deleted_on_is_before_cutoff(self):
        case = _create_case(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(case.case_id, self.domain)

    def test_case_is_not_hard_deleted_if_deleted_on_is_cutoff(self):
        case = _create_case(self.domain, deleted_on=self.cutoff)

        CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        fetched_case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertIsNotNone(fetched_case)

    def test_case_is_not_hard_deleted_if_deleted_on_is_after_cutoff(self):
        case = _create_case(self.domain, deleted_on=datetime(2020, 1, 1, 12, 31))

        CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        fetched_case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertIsNotNone(fetched_case)

    def test_case_is_not_hard_deleted_if_deleted_on_is_null(self):
        case = _create_case(self.domain, deleted_on=None)

        CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        fetched_case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertIsNotNone(fetched_case)

    def test_returns_deleted_counts(self):
        expected_count = 5
        for _ in range(expected_count):
            _create_case(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        counts = CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        self.assertEqual(counts, {'form_processor.CaseTransaction': 5, 'form_processor.CommCareCase': 5})

    def test_nothing_is_deleted_if_dry_run_is_true(self):
        case = _create_case(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        # dry_run defaults to True
        counts = CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff)

        # should not raise CaseNotFound
        CommCareCase.objects.get_case(case.case_id, self.domain)
        # still returns accurate count
        self.assertEqual(counts, {'form_processor.CommCareCase': 1})

    def test_tombstone_is_created_on_deletion(self):
        case = _create_case(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)
        delete_doc = DeletedSQLDoc.objects.filter(doc_id=case.case_id)

        self.assertIsNotNone(delete_doc)

    def test_tombstone_count_matches_deleted_case_count(self):
        expected_count = 5
        for _ in range(expected_count):
            _create_case(self.domain, deleted_on=datetime(2020, 1, 1, 12, 29))

        counts = CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        self.assertEqual(DeletedSQLDoc.objects.all().count(), counts['form_processor.CommCareCase'])

    def test_tombstone_is_not_created_if_deleted_on_is_null(self):
        _create_case(self.domain, deleted_on=None)

        CommCareCase.objects.hard_delete_cases_before_cutoff(self.cutoff, dry_run=False)

        self.assertEqual(DeletedSQLDoc.objects.count(), 0)


@sharded
class TestCommCareCase(BaseCaseManagerTest):

    def test_closed_transactions(self):
        case = _create_case()
        _create_case_transactions(case)

        self.assertEqual(len(case.get_closing_transactions()), 1)
        self.assertTrue(case.get_closing_transactions()[0].is_case_close)

    def test_closed_transactions_with_tracked(self):
        case = _create_case()
        _create_case_transactions(case)

        case.track_create(CaseTransaction(
            case=case,
            form_id=uuid.uuid4().hex,
            server_date=datetime.utcnow(),
            type=CaseTransaction.TYPE_FORM | CaseTransaction.TYPE_CASE_CLOSE,
            revoked=True
        ))
        # exclude based on type
        case.track_create(CaseTransaction(
            case=case,
            form_id=uuid.uuid4().hex,
            server_date=datetime.utcnow(),
            type=CaseTransaction.TYPE_FORM | CaseTransaction.TYPE_CASE_ATTACHMENT,
            revoked=False
        ))
        self.assertEqual(len(case.get_closing_transactions()), 2)

    def test_get_index_map(self):
        mother_id = uuid.uuid4().hex
        task_id = uuid.uuid4().hex
        with self.get_case_and_indices(
            mother_id=mother_id,
            task_id=task_id,
        ) as (case, index1, index2):
            index_map = case.get_index_map()
            self.assertEqual(index_map, {
                'parent': {
                    'case_id': mother_id,
                    'case_type': 'mother',
                    'relationship': 'child',
                },
                'task': {
                    'case_id': task_id,
                    'case_type': 'task',
                    'relationship': 'extension',
                },
            })

    def test_get_index_map_reversed(self):
        with self.get_case_and_indices(
            mother_id=uuid.uuid4().hex,
            task_id=uuid.uuid4().hex,
        ) as (case, index1, index2):
            index_map = case.get_index_map(reversed=True)
            self.assertEqual(index_map, {})  # Nothing indexes `case`

    @override_settings(UNIT_TESTING=False)
    def test_delete_creates_tombstone_by_default(self):
        case = _create_case(deleted_on=datetime.now())
        case.delete()
        self.assertEqual(DeletedSQLDoc.objects.all().count(), 1)

    @override_settings(UNIT_TESTING=False)
    def test_delete_raises_error_if_leave_tombstone_is_false(self):
        case = _create_case(deleted_on=datetime.now())
        with self.assertRaises(ValueError):
            case.delete(leave_tombstone=False)


@sharded
class TestCaseAttachmentManager(BaseCaseManagerTest):

    def setUp(self):
        super().setUp()
        self.using = router.db_for_read(CaseAttachment, **{HINT_PLPROXY: True})

    def test_get_attachments(self):
        case = _create_case()

        case.track_create(CaseAttachment(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='pic.jpg',
            content_type='image/jpeg',
            blob_id='125',
            md5='123',
        ))
        case.track_create(CaseAttachment(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml',
            blob_id='126',
            md5='123',
        ))
        case.save(with_tracked_models=True)

        with self.assertNumQueries(1, using=case.db):
            attachments = CaseAttachment.objects.get_attachments(case.case_id)

        self.assertEqual(2, len(attachments))
        sorted_attachments = sorted(attachments, key=lambda x: x.name)
        for att in attachments:
            self.assertEqual(case.case_id, att.case_id)
        self.assertEqual('doc', sorted_attachments[0].name)
        self.assertEqual('pic.jpg', sorted_attachments[1].name)

    def test_get_attachment_by_name(self):
        case = _create_case()

        case.track_create(CaseAttachment(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='pic.jpg',
            content_type='image/jpeg',
            blob_id='123',
            md5='123'
        ))
        case.track_create(CaseAttachment(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='my_doc',
            content_type='text/xml',
            blob_id='124',
            md5='123'
        ))
        case.save(with_tracked_models=True)

        with self.assertRaises(AttachmentNotFound):
            CaseAttachment.objects.get_attachment_by_name(case.case_id, 'missing')

        with self.assertNumQueries(1, using=self.using):
            attachment_meta = CaseAttachment.objects.get_attachment_by_name(case.case_id, 'pic.jpg')

        self.assertEqual(case.case_id, attachment_meta.case_id)
        self.assertEqual('pic.jpg', attachment_meta.name)
        self.assertEqual('image/jpeg', attachment_meta.content_type)


@sharded
class TestCommCareCaseIndexManager(BaseCaseManagerTest):

    def test_get_indices(self):
        with self.get_case_and_indices(
            mother_id=uuid.uuid4().hex,
            task_id=uuid.uuid4().hex,
        ) as (case, index1, index2):
            indices = CommCareCaseIndex.objects.get_indices(
                case.domain,
                case.case_id,
            )
            indices.sort(key=lambda x: x.identifier)  # "parent" comes before "task"
            self.assertEqual([index1, index2], indices)

    def test_get_reverse_indices(self):
        referenced_case_id = uuid.uuid4().hex
        case, index = _create_case_with_index(referenced_case_id)
        index.referenced_id = index.case_id  # see CommCareCaseIndex.objects.get_reverse_indices
        _create_case_with_index(referenced_case_id, case_is_deleted=True)
        indices = CommCareCaseIndex.objects.get_reverse_indices(DOMAIN, referenced_case_id)
        self.assertEqual([index], indices)

    def test_get_all_reverse_indices_info(self):
        referenced_id1 = uuid.uuid4().hex
        referenced_id2 = uuid.uuid4().hex
        with self.get_case_and_indices(
            mother_id=referenced_id2,
            task_id=referenced_id1,
        ) as (case, child_index, extension_index):

            # Create irrelevant case and index
            _create_case_with_index(case.case_id)

            # create index on deleted case
            _create_case_with_index(referenced_id1, case_is_deleted=True)

            self.assertEqual(
                set(CommCareCaseIndex.objects.get_all_reverse_indices_info(
                    DOMAIN,
                    [referenced_id1, referenced_id2],
                )),
                {
                    CaseIndexInfo(
                        case_id=case.case_id,
                        identifier='task',
                        referenced_id=referenced_id1,
                        referenced_type='task',
                        relationship=CommCareCaseIndex.EXTENSION,
                    ),
                    CaseIndexInfo(
                        case_id=case.case_id,
                        identifier='parent',
                        referenced_id=referenced_id2,
                        referenced_type='mother',
                        relationship=CommCareCaseIndex.CHILD
                    ),
                }
            )

    def test_get_extension_case_ids(self):
        # There are similar tests for get_extension_case_ids in the
        # `.test_extension_cases` module, but none that replicate this
        # one precisely. This one may also be better because it creates
        # models directly rather creating cases by constructing and
        # processing form XML.

        # Create case and index
        referenced_id = uuid.uuid4().hex
        case, _ = _create_case_with_index(referenced_id, identifier='task', referenced_type='task',
                                relationship_id=CommCareCaseIndex.EXTENSION)

        # Create irrelevant cases
        _create_case_with_index(referenced_id)
        _create_case_with_index(referenced_id, identifier='task', referenced_type='task',
                                relationship_id=CommCareCaseIndex.EXTENSION, case_is_deleted=True)

        self.assertEqual(
            CommCareCaseIndex.objects.get_extension_case_ids(DOMAIN, [referenced_id]),
            [case.case_id],
        )


class TestCaseTransactionManager(BaseCaseManagerTest):

    def test_get_transactions(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)
        transactions = CaseTransaction.objects.get_transactions(case.case_id)
        self.assertEqual(1, len(transactions))
        self.assertEqual(form_id, transactions[0].form_id)

        form_ids = _create_case_transactions(case, all_forms=True)

        transactions = CaseTransaction.objects.get_transactions(case.case_id)
        self.assertEqual({t.form_id for t in transactions}, {form_id} | form_ids)
        self.assertEqual(len(transactions), 6)

    def test_get_transaction_by_form_id(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)

        transaction = CaseTransaction.objects.get_transaction_by_form_id(case.case_id, form_id)
        self.assertEqual(form_id, transaction.form_id)
        self.assertEqual(case.case_id, transaction.case_id)

        transaction = CaseTransaction.objects.get_transaction_by_form_id(case.case_id, 'wrong')
        self.assertIsNone(transaction)

    def test_get_most_recent_form_transaction(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)

        transaction = CaseTransaction.objects.get_most_recent_form_transaction(case.case_id)
        self.assertEqual(transaction.form_id, form_id)

        case.track_create(CaseTransaction(
            case=case,
            form_id=uuid.uuid4().hex,
            server_date=datetime.utcnow(),
            type=CaseTransaction.TYPE_REBUILD_FORM_ARCHIVED,
            revoked=False
        ))
        case.save(with_tracked_models=True)

        transaction = CaseTransaction.objects.get_most_recent_form_transaction(case.case_id)
        # still the same since the last transaction was not a form transaction
        self.assertEqual(transaction.form_id, form_id)

        second_form_id = uuid.uuid4().hex
        case.track_create(CaseTransaction(
            case=case,
            form_id=second_form_id,
            server_date=datetime.utcnow(),
            type=CaseTransaction.TYPE_FORM,
            revoked=False
        ))
        case.save(with_tracked_models=True)

        transaction = CaseTransaction.objects.get_most_recent_form_transaction(case.case_id)
        # now it's the new form transaction
        self.assertEqual(transaction.form_id, second_form_id)

        case.track_create(CaseTransaction(
            case=case,
            form_id=uuid.uuid4().hex,
            server_date=datetime.utcnow(),
            type=CaseTransaction.TYPE_FORM,
            revoked=True
        ))
        case.save(with_tracked_models=True)

        transaction = CaseTransaction.objects.get_most_recent_form_transaction(case.case_id)
        # still second_form_id since the newest one is revoked
        self.assertEqual(transaction.form_id, second_form_id)

    def test_get_transactions_for_case_rebuild(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)
        form_ids = _create_case_transactions(case)

        transactions = CaseTransaction.objects.get_transactions_for_case_rebuild(case.case_id)
        self.assertEqual({t.form_id for t in transactions}, {form_id} | form_ids)
        self.assertEqual(4, len(transactions))

    def test_case_has_transactions_since_sync(self):
        case1 = _create_case()
        _create_case_transactions(case1)
        self.assertTrue(CaseTransaction.objects.case_has_transactions_since_sync(
            case1.case_id, "foo", datetime(1992, 1, 30)))
        self.assertFalse(CaseTransaction.objects.case_has_transactions_since_sync(
            case1.case_id, "foo", datetime.utcnow()))

    def test_exists_for_form(self):
        self.assertFalse(CaseTransaction.objects.exists_for_form('missing-form'))

        case = _create_case()
        for form_id in _create_case_transactions(case):
            self.assertTrue(CaseTransaction.objects.exists_for_form(form_id))


def _create_case(domain=DOMAIN, **kw):
    return create_case(domain, save=True, **kw)


def _create_case_with_index(*args, **kw):
    return create_case_with_index(DOMAIN, save=True, *args, **kw)


def _create_case_transactions(case, all_forms=False):
    TX = CaseTransaction
    traces = [
        CaseTransactionTrace(TX.TYPE_FORM | TX.TYPE_CASE_CREATE | TX.TYPE_LEDGER),
        CaseTransactionTrace(TX.TYPE_FORM | TX.TYPE_LEDGER),
        CaseTransactionTrace(TX.TYPE_FORM | TX.TYPE_CASE_CLOSE),
        CaseTransactionTrace(TX.TYPE_FORM, revoked=True, include=all_forms),  # excluded because revoked
        CaseTransactionTrace(TX.TYPE_REBUILD_FORM_ARCHIVED, include=all_forms),  # excluded based on type
    ]
    for trace in traces:
        case.track_create(CaseTransaction(
            case=case,
            form_id=trace.form_id,
            server_date=datetime.utcnow(),
            type=trace.type,
            revoked=trace.revoked,
        ))
    case.save(with_tracked_models=True)
    return {t.form_id for t in traces if t.include}


@attr.s
class CaseTransactionTrace:
    type = attr.ib()
    revoked = attr.ib(default=False)
    include = attr.ib(default=True)
    form_id = attr.ib(factory=lambda: uuid.uuid4().hex)
