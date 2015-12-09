import uuid
from datetime import datetime

from django.test import TestCase

from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.exceptions import AttachmentNotFound, CaseNotFound, CaseSaveError
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, \
    CaseTransaction, CommCareCaseIndexSQL, CaseAttachmentSQL, SupplyPointCaseMixin
from crispy_forms.tests.utils import override_settings

DOMAIN = 'test-case-accessor'


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class CaseAccessorTestsSQL(TestCase):
    dependent_apps = []

    def test_get_case_by_id(self):
        case = _create_case()
        with self.assertNumQueries(1):
            case = CaseAccessorSQL.get_case(case.case_id)
        self.assertIsNotNone(case)
        self.assertIsInstance(case, CommCareCaseSQL)
        self.assertEqual(DOMAIN, case.domain)
        self.assertEqual('user1', case.owner_id)

    def test_get_case_by_id_missing(self):
        with self.assertRaises(CaseNotFound):
            CaseAccessorSQL.get_case('missing_case')

    def test_get_cases(self):
        case1 = _create_case()
        case2 = _create_case()

        cases = CaseAccessorSQL.get_cases(['missing_case'])
        self.assertEqual([], cases)

        cases = CaseAccessorSQL.get_cases([case1.case_id])
        self.assertEqual(1, len(cases))
        self.assertEqual(case1.case_id, cases[0].case_id)

        cases = CaseAccessorSQL.get_cases([case1.case_id, case2.case_id], ordered=True)
        self.assertEqual(2, len(cases))
        self.assertEqual(case1.case_id, cases[0].case_id)
        self.assertEqual(case2.case_id, cases[1].case_id)

    def test_case_modified_since(self):
        case = _create_case()

        self.assertFalse(CaseAccessorSQL.case_modified_since(case.case_id, case.server_modified_on))

        self.assertTrue(CaseAccessorSQL.case_modified_since(case.case_id, datetime.utcnow()))

    def test_get_case_xform_ids(self):
        form_id1 = uuid.uuid4().hex
        case = _create_case(form_id=form_id1)

        form_ids = _create_case_transactions(case)

        self.assertEqual([form_id1, form_ids[0]], CaseAccessorSQL.get_case_xform_ids(case.case_id))

    def test_get_indices(self):
        case = _create_case()
        index1 = CommCareCaseIndexSQL(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndexSQL.CHILD
        )
        case.track_create(index1)
        index2 = CommCareCaseIndexSQL(
            case=case,
            identifier='task',
            referenced_type='task',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndexSQL.EXTENSION
        )
        case.track_create(index2)

        CaseAccessorSQL.save_case(case)

        indices = CaseAccessorSQL.get_indices(case.case_id)
        self.assertEqual(2, len(indices))
        self.assertEqual([index1, index2], indices)

    def test_get_reverse_indices(self):
        case = _create_case()

        referenced_case_id = uuid.uuid4().hex

        index1 = CommCareCaseIndexSQL(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=referenced_case_id,
            relationship_id=CommCareCaseIndexSQL.CHILD
        )
        case.track_create(index1)

        CaseAccessorSQL.save_case(case)

        indices = CaseAccessorSQL.get_reverse_indices(referenced_case_id)
        self.assertEqual(1, len(indices))
        self.assertEqual(index1, indices[0])

    def test_get_reverse_indexed_cases(self):
        def _create_case_with_index(referenced_case_id):
            case = _create_case()

            index1 = CommCareCaseIndexSQL(
                case=case,
                identifier='parent',
                referenced_type='mother',
                referenced_id=referenced_case_id,
                relationship_id=CommCareCaseIndexSQL.CHILD
            )
            case.track_create(index1)

            CaseAccessorSQL.save_case(case)
            return case.case_id

        referenced_case_ids = [uuid.uuid4().hex, uuid.uuid4().hex]
        expected_case_ids = [_create_case_with_index(case_id) for case_id in referenced_case_ids]
        cases = CaseAccessorSQL.get_reverse_indexed_cases(DOMAIN, referenced_case_ids)
        self.assertEqual(2, len(cases))
        self.assertEqual(set(expected_case_ids), {c.case_id for c in cases})

    def test_hard_delete_case(self):
        case1 = _create_case()
        case2 = _create_case(domain='other_domain')
        self.addCleanup(lambda: CaseAccessorSQL.hard_delete_cases('other_domain', [case2.case_id]))

        case1.track_create(CommCareCaseIndexSQL(
            case=case1,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndexSQL.CHILD
        ))
        case1.track_create(CaseAttachmentSQL(
            case=case1,
            attachment_id=uuid.uuid4().hex,
            name='pic.jpg',
            content_type='image/jpeg'
        ))
        CaseAccessorSQL.save_case(case1)

        num_deleted = CaseAccessorSQL.hard_delete_cases(DOMAIN, [case1.case_id, case2.case_id])
        self.assertEqual(1, num_deleted)
        with self.assertRaises(CaseNotFound):
            CaseAccessorSQL.get_case(case1.case_id)

        self.assertEqual([], CaseAccessorSQL.get_indices(case1.case_id))
        self.assertEqual([], CaseAccessorSQL.get_attachments(case1.case_id))
        self.assertEqual([], CaseAccessorSQL.get_transactions(case1.case_id))

    def test_get_attachment_by_name(self):
        case = _create_case()

        case.track_create(CaseAttachmentSQL(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='pic.jpg',
            content_type='image/jpeg'
        ))
        case.track_create(CaseAttachmentSQL(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml'
        ))
        CaseAccessorSQL.save_case(case)

        with self.assertRaises(AttachmentNotFound):
            CaseAccessorSQL.get_attachment_by_name(case.case_id, 'missing')

        with self.assertNumQueries(1):
            attachment_meta = CaseAccessorSQL.get_attachment_by_name(case.case_id, 'pic.jpg')

        self.assertEqual(case.case_id, attachment_meta.case_id)
        self.assertEqual('pic.jpg', attachment_meta.name)
        self.assertEqual('image/jpeg', attachment_meta.content_type)

    def test_get_attachments(self):
        case = _create_case()

        case.track_create(CaseAttachmentSQL(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='pic.jpg',
            content_type='image/jpeg'
        ))
        case.track_create(CaseAttachmentSQL(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml'
        ))
        CaseAccessorSQL.save_case(case)

        with self.assertRaises(AttachmentNotFound):
            CaseAccessorSQL.get_attachment_by_name(case.case_id, 'missing')

        with self.assertNumQueries(1):
            attachments = CaseAccessorSQL.get_attachments(case.case_id)

        self.assertEqual(2, len(attachments))
        sorted_attachments = sorted(attachments, key=lambda x: x.name)
        for att in attachments:
            self.assertEqual(case.case_id, att.case_id)
        self.assertEqual('doc', sorted_attachments[0].name)
        self.assertEqual('pic.jpg', sorted_attachments[1].name)

    def test_get_transactions(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)
        transactions = CaseAccessorSQL.get_transactions(case.case_id)
        self.assertEqual(1, len(transactions))
        self.assertEqual(form_id, transactions[0].form_id)

        form_ids = _create_case_transactions(case)

        transactions = CaseAccessorSQL.get_transactions(case.case_id)
        self.assertEqual(4, len(transactions))
        self.assertEqual([form_id] + form_ids, [t.form_id for t in transactions])

    def test_get_transactions_for_case_rebuild(self):
        form_id = uuid.uuid4().hex
        case = _create_case(form_id=form_id)
        form_ids = _create_case_transactions(case)

        transactions = CaseAccessorSQL.get_transactions_for_case_rebuild(case.case_id)
        self.assertEqual(2, len(transactions))
        self.assertEqual([form_id, form_ids[0]], [t.form_id for t in transactions])

    def test_get_case_by_location(self):
        case = _create_case(case_type=SupplyPointCaseMixin.CASE_TYPE)
        location_id = uuid.uuid4().hex
        case.location_id = location_id
        CaseAccessorSQL.save_case(case)

        fetched_case = CaseAccessorSQL.get_case_by_location(DOMAIN, location_id)
        self.assertEqual(case.id, fetched_case.id)

    def test_get_case_ids_in_domain(self):
        case1 = _create_case(case_type='t1')
        case2 = _create_case(case_type='t1')
        case3 = _create_case(case_type='t2')

        case_ids = CaseAccessorSQL.get_case_ids_in_domain(DOMAIN)
        self.assertEqual({case1.case_id, case2.case_id, case3.case_id}, set(case_ids))

        case_ids = CaseAccessorSQL.get_case_ids_in_domain(DOMAIN, 't1')
        self.assertEqual({case1.case_id, case2.case_id}, set(case_ids))

        case2.domain = 'new_domain'
        CaseAccessorSQL.save_case(case2)

        case_ids = CaseAccessorSQL.get_case_ids_in_domain(DOMAIN)
        self.assertEqual({case1.case_id, case3.case_id}, set(case_ids))

    def test_save_case_update_index(self):
        case = _create_case()

        original_index = CommCareCaseIndexSQL(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndexSQL.CHILD
        )
        case.track_create(original_index)
        CaseAccessorSQL.save_case(case)

        [index] = CaseAccessorSQL.get_indices(case.case_id)
        index.identifier = 'new_identifier'  # shouldn't get saved
        index.referenced_type = 'new_type'
        index.referenced_id = uuid.uuid4().hex
        index.relationship_id = CommCareCaseIndexSQL.EXTENSION
        case.track_update(index)
        CaseAccessorSQL.save_case(case)

        [updated_index] = CaseAccessorSQL.get_indices(case.case_id)
        self.assertEqual(updated_index.id, index.id)
        self.assertEqual(updated_index.identifier, original_index.identifier)
        self.assertEqual(updated_index.referenced_type, index.referenced_type)
        self.assertEqual(updated_index.referenced_id, index.referenced_id)
        self.assertEqual(updated_index.relationship_id, index.relationship_id)

    def test_save_case_delete_index(self):
        case = _create_case()

        case.track_create(CommCareCaseIndexSQL(
            case=case,
            identifier='parent',
            referenced_type='mother',
            referenced_id=uuid.uuid4().hex,
            relationship_id=CommCareCaseIndexSQL.CHILD
        ))
        CaseAccessorSQL.save_case(case)

        [index] = CaseAccessorSQL.get_indices(case.case_id)
        case.track_delete(index)
        CaseAccessorSQL.save_case(case)
        self.assertEqual([], CaseAccessorSQL.get_indices(case.case_id))

    def test_save_case_delete_attachment(self):
        case = _create_case()

        case.track_create(CaseAttachmentSQL(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml'
        ))
        CaseAccessorSQL.save_case(case)

        [attachment] = CaseAccessorSQL.get_attachments(case.case_id)
        case.track_delete(attachment)
        CaseAccessorSQL.save_case(case)
        self.assertEqual([], CaseAccessorSQL.get_attachments(case.case_id))

    def test_save_case_update_attachment(self):
        case = _create_case()

        case.track_create(CaseAttachmentSQL(
            case=case,
            attachment_id=uuid.uuid4().hex,
            name='doc',
            content_type='text/xml'
        ))
        CaseAccessorSQL.save_case(case)

        [attachment] = CaseAccessorSQL.get_attachments(case.case_id)
        attachment.name = 'new_name'

        # hack to call the sql function with an already saved attachment
        case.track_create(attachment)

        with self.assertRaises(CaseSaveError):
            CaseAccessorSQL.save_case(case)

    def test_save_case_update_transaction(self):
        case = _create_case()

        [transaction] = CaseAccessorSQL.get_transactions(case.case_id)
        transaction.revoked = True

        # hack to call the sql function with an already saved transaction
        case.track_create(transaction)

        with self.assertRaises(CaseSaveError):
            CaseAccessorSQL.save_case(case)


def _create_case(domain=None, form_id=None, case_type=None):
    """
    Create the models directly so that these tests aren't dependent on any
    other apps. Not testing form processing here anyway.
    :return: case_id
    """
    domain = domain or DOMAIN
    form_id = form_id or uuid.uuid4().hex
    case_id = uuid.uuid4().hex
    user_id = 'user1'
    utcnow = datetime.utcnow()

    form = XFormInstanceSQL(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain
    )

    cases = []
    if case_id:
        case = CommCareCaseSQL(
            case_id=case_id,
            domain=domain,
            type=case_type or '',
            owner_id=user_id,
            opened_on=utcnow,
            modified_on=utcnow,
            modified_by=user_id,
            server_modified_on=utcnow,
        )
        case.track_create(CaseTransaction.form_transaction(case, form))
        cases = [case]

    FormProcessorSQL.save_processed_models([form], cases)
    return CaseAccessorSQL.get_case(case_id)


def _create_case_transactions(case):
    case.track_create(CaseTransaction(
        case=case,
        form_id=uuid.uuid4().hex,
        server_date=datetime.utcnow(),
        type=CaseTransaction.TYPE_FORM,
        revoked=False
    ))
    # exclude revoked
    case.track_create(CaseTransaction(
        case=case,
        form_id=uuid.uuid4().hex,
        server_date=datetime.utcnow(),
        type=CaseTransaction.TYPE_FORM,
        revoked=True
    ))
    # exclude based on type
    case.track_create(CaseTransaction(
        case=case,
        form_id=uuid.uuid4().hex,
        server_date=datetime.utcnow(),
        type=CaseTransaction.TYPE_REBUILD_FORM_ARCHIVED,
        revoked=False
    ))
    form_ids = [t.form_id for t in case.get_tracked_models_to_create(CaseTransaction)]
    CaseAccessorSQL.save_case(case)
    return form_ids
