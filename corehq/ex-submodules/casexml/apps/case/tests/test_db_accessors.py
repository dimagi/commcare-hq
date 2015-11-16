import uuid

from casexml.apps.case.const import CASE_INDEX_CHILD, CASE_INDEX_EXTENSION
from casexml.apps.case.dbaccessors.related import get_extension_case_ids, \
    get_indexed_case_ids, get_reverse_indexed_cases, get_reverse_indices_json
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.sharedmodels import CommCareCaseIndex
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.hqcase.dbaccessors import get_total_case_count
from django.test import TestCase


class TestCaseByOwner(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_cases()

    def testCountZero(self):
        self.assertEqual(0, get_total_case_count())

    def testCountNonZero(self):
        CommCareCase().save()
        CommCareCase().save()
        self.assertEqual(2, get_total_case_count())
        delete_all_cases()


class TestExtensionCaseIds(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_cases()

    def setUp(self):
        self.domain = 'domain'
        self.factory = CaseFactory(self.domain)

    def test_no_extensions(self):
        """ Returns empty when there are other index types """
        parent_id = uuid.uuid4().hex
        child_id = uuid.uuid4().hex
        parent = CaseStructure(case_id=parent_id)

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=child_id,
                indices=[
                    CaseIndex(parent, relationship=CASE_INDEX_CHILD)
                ]
            )
        )
        returned_cases = get_extension_case_ids(self.domain, [parent_id])
        self.assertEqual(returned_cases, [])

    def test_simple_extension_returned(self):
        """ Should return extension if it exists """
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        host = CaseStructure(case_id=host_id)

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION)
                ]
            )
        )
        returned_cases = get_extension_case_ids(self.domain, [host_id])
        self.assertItemsEqual(returned_cases, [extension_id])

    def test_extension_of_multiple_hosts_returned(self):
        """ Should return an extension from any host if there are multiple indices """
        host_id = uuid.uuid4().hex
        host_2_id = uuid.uuid4().hex
        parent_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        host = CaseStructure(case_id=host_id)
        host_2 = CaseStructure(case_id=host_2_id)
        parent = CaseStructure(case_id=parent_id)

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                    CaseIndex(host_2, relationship=CASE_INDEX_EXTENSION, identifier="host_2"),
                    CaseIndex(parent, relationship=CASE_INDEX_CHILD),
                ]
            )
        )

        returned_cases = get_extension_case_ids(self.domain, [host_2_id])
        self.assertItemsEqual(returned_cases, [extension_id])
        returned_cases = get_extension_case_ids(self.domain, [host_id])
        self.assertItemsEqual(returned_cases, [extension_id])

    def test_host_with_multiple_extensions(self):
        """ Return all extensions from a single host """
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        extension_2_id = uuid.uuid4().hex

        host = CaseStructure(case_id=host_id)

        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ]
            ),
            CaseStructure(
                case_id=extension_2_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ]
            ),
        ]
        )

        returned_cases = get_extension_case_ids(self.domain, [host_id])
        self.assertItemsEqual(returned_cases, [extension_id, extension_2_id])

    def test_extensions_from_list(self):
        """ Given a list of hosts, should return all extensions """
        host_id = uuid.uuid4().hex
        host_2_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        extension_2_id = uuid.uuid4().hex

        host = CaseStructure(case_id=host_id)
        host_2 = CaseStructure(case_id=host_2_id)
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ]
            )
        )
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_2_id,
                indices=[
                    CaseIndex(host_2, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ]
            )
        )
        returned_cases = get_extension_case_ids(self.domain, [host_id, host_2_id])
        self.assertItemsEqual(returned_cases, [extension_id, extension_2_id])


class TestIndexedCaseIds(TestCase):
    @classmethod
    def setUpClass(cls):
        delete_all_cases()

    def setUp(self):
        self.domain = 'domain'
        self.factory = CaseFactory(self.domain)

    def test_indexed_case_ids_returns_extensions(self):
        """ When getting indices, also return extensions """
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        host = CaseStructure(case_id=host_id)

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION)
                ]
            )
        )
        returned_cases = get_indexed_case_ids(self.domain, [extension_id])
        self.assertItemsEqual(returned_cases, [host_id])


class TestReverseIndexedCases(TestCase):
    @classmethod
    def setUpClass(cls):
        delete_all_cases()

    def setUp(self):
        self.domain = 'domain'
        self.factory = CaseFactory(self.domain)
        self.indexed_case_id = uuid.uuid4().hex
        self.index = CommCareCaseIndex(
            identifier="host",
            referenced_type="host",
            relationship=CASE_INDEX_EXTENSION,
            referenced_id=self.indexed_case_id
        )
        self.case = CommCareCase(domain=self.domain, indices=[self.index])
        self.case.save()

    def _delete_relationship(self):
        del self.case.indices[0].relationship
        self.case.save()

    def test_legacy_reverse_index(self):
        """Test that cases with indices without a relationship are still returned"""
        self.assertEqual(
            [self.case._id],
            [c._id for c in
             get_reverse_indexed_cases(self.domain, [self.indexed_case_id], relationship=CASE_INDEX_EXTENSION)])
        # remove the relationship and make sure the case is still returned when asking for child indexes
        self._delete_relationship()
        self.assertEqual(
            [self.case._id],
            [c._id for c in get_reverse_indexed_cases(self.domain, [self.indexed_case_id])])
        # make sure it doesn't show up if we are asking for extension indexes
        self.assertEqual(
            [],
            [c._id for c in
             get_reverse_indexed_cases(self.domain, [self.indexed_case_id], CASE_INDEX_EXTENSION)])

    def test_legacy_reverse_index_json(self):
        expected_returned_json = [{
            'doc_type': 'CommCareCaseIndex',
            'identifier': self.index.identifier,
            'relationship': self.index.relationship,
            'referenced_type': self.index.referenced_type,
            'referenced_id': self.case._id
        }]
        self.assertEqual(
            expected_returned_json,
            get_reverse_indices_json(self.domain, self.indexed_case_id, relationship=CASE_INDEX_EXTENSION))

        self._delete_relationship()
        # it should now be a child relationship
        expected_returned_json[0]['relationship'] = CASE_INDEX_CHILD
        self.assertEqual(expected_returned_json, get_reverse_indices_json(self.domain, self.indexed_case_id))
