import uuid
from datetime import datetime

import attr

from django.conf import settings
from django.db import router
from django.test import TestCase

from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import AttachmentNotFound, CaseNotFound, CaseSaveError
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import (
    CaseAttachment,
    CaseTransaction,
    CommCareCase,
    CommCareCaseIndex,
    XFormInstance,
)
from corehq.form_processor.models.cases import CaseIndexInfo
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.sql_db.routers import HINT_PLPROXY
from corehq.sql_db.util import get_db_alias_for_partitioned_doc

DOMAIN = 'test-case-accessor'


class BaseCaseManagerTest(TestCase):

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_sql_forms(DOMAIN)
            FormProcessorTestUtils.delete_all_sql_cases(DOMAIN)
        super(BaseCaseManagerTest, self).tearDown()


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

    def test_get_case_ids_that_exist(self):
        case1 = _create_case()
        case2 = _create_case()

        case_ids = CommCareCase.objects.get_case_ids_that_exist(
            DOMAIN,
            ['missing_case', case1.case_id, case2.case_id]
        )
        self.assertItemsEqual(case_ids, [case1.case_id, case2.case_id])

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
        case = _create_case()
        index1 = CommCareCaseIndex(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndex.CHILD
        )
        case.track_create(index1)
        index2 = CommCareCaseIndex(
            case=case,
            identifier='task',
            referenced_type='task',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndex.EXTENSION
        )
        case.track_create(index2)
        case.save(with_tracked_models=True)

        indices = CommCareCaseIndex.objects.get_indices(case.domain, case.case_id)
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
        # Create case and indexes
        case = _create_case()
        referenced_id1 = uuid.uuid4().hex
        referenced_id2 = uuid.uuid4().hex
        extension_index = CommCareCaseIndex(
            case=case,
            identifier="task",
            referenced_type="task",
            referenced_id=referenced_id1,
            relationship_id=CommCareCaseIndex.EXTENSION
        )
        case.track_create(extension_index)
        child_index = CommCareCaseIndex(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=referenced_id2,
            relationship_id=CommCareCaseIndex.CHILD
        )
        case.track_create(child_index)
        case.save(with_tracked_models=True)

        # Create irrelevant case and index
        _create_case_with_index(case.case_id)

        # create index on deleted case
        _create_case_with_index(referenced_id1, case_is_deleted=True)

        self.assertEqual(
            set(CommCareCaseIndex.objects.get_all_reverse_indices_info(DOMAIN, [referenced_id1, referenced_id2])),
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


def _create_case(domain=DOMAIN, form_id=None, case_type=None, user_id='user1', closed=False, case_id=None):
    """Create case and related models directly (not via form processor)

    :return: CommCareCase
    """
    form_id = form_id or uuid.uuid4().hex
    case_id = case_id or uuid.uuid4().hex
    utcnow = datetime.utcnow()
    form = XFormInstance(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain
    )
    case = CommCareCase(
        case_id=case_id,
        domain=domain,
        type=case_type or '',
        owner_id=user_id,
        opened_on=utcnow,
        modified_on=utcnow,
        modified_by=user_id,
        server_modified_on=utcnow,
        closed=closed or False
    )
    case.track_create(CaseTransaction.form_transaction(case, form, utcnow))
    FormProcessorSQL.save_processed_models(ProcessedForms(form, None), [case])
    return case


def _create_case_with_index(referenced_case_id, identifier='parent', referenced_type='mother',
                            relationship_id=CommCareCaseIndex.CHILD, case_is_deleted=False,
                            case_type='child'):
    case = _create_case(case_type=case_type)
    case.deleted = case_is_deleted
    index = CommCareCaseIndex(
        case=case,
        identifier=identifier,
        referenced_type=referenced_type,
        referenced_id=referenced_case_id,
        relationship_id=relationship_id
    )
    case.track_create(index)
    case.save(with_tracked_models=True)
    return case, index


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
