import uuid

from django.conf import settings
from django.test import TestCase

from casexml.apps.case.const import CASE_INDEX_CHILD, CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.form_processor.models import CommCareCaseIndex
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded


@sharded
class TestExtensionCaseIds(TestCase):

    def setUp(self):
        super(TestExtensionCaseIds, self).setUp()
        self.domain = 'domain'
        FormProcessorTestUtils.delete_all_cases()
        self.factory = CaseFactory(self.domain)

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_cases()
            FormProcessorTestUtils.delete_all_xforms()
        super(TestExtensionCaseIds, self).tearDown()

    def test_no_extensions(self):
        """ Returns empty when there are other index types """
        parent_id = uuid.uuid4().hex
        child_id = uuid.uuid4().hex
        parent = CaseStructure(case_id=parent_id, attrs={'create': True})

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=child_id,
                indices=[
                    CaseIndex(parent, relationship=CASE_INDEX_CHILD)
                ],
                attrs={'create': True}
            )
        )
        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(self.domain, [parent_id])
        self.assertEqual(returned_cases, [])

    def test_simple_extension_returned(self):
        """ Should return extension if it exists """
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        host = CaseStructure(case_id=host_id, attrs={'create': True})

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION)
                ],
                attrs={'create': True}
            )
        )
        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(self.domain, [host_id])
        self.assertItemsEqual(returned_cases, [extension_id])
        # exclude_for_case_type should exclude the result
        self.assertEqual(
            CommCareCaseIndex.objects.get_extension_case_ids(
                self.domain, [host_id], exclude_for_case_type=CaseIndex.DEFAULT_RELATED_CASE_TYPE),
            []
        )

    def test_extension_of_multiple_hosts_returned(self):
        """ Should return an extension from any host if there are multiple indices """
        host_id = uuid.uuid4().hex
        host_2_id = uuid.uuid4().hex
        parent_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        host = CaseStructure(case_id=host_id, attrs={'create': True})
        host_2 = CaseStructure(case_id=host_2_id, attrs={'create': True})
        parent = CaseStructure(case_id=parent_id, attrs={'create': True})

        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                    CaseIndex(host_2, relationship=CASE_INDEX_EXTENSION, identifier="host_2"),
                    CaseIndex(parent, relationship=CASE_INDEX_CHILD),
                ],
                attrs={'create': True}
            )
        )

        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(self.domain, [host_2_id])
        self.assertItemsEqual(returned_cases, [extension_id])
        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(self.domain, [host_id])
        self.assertItemsEqual(returned_cases, [extension_id])

    def test_host_with_multiple_extensions(self):
        """ Return all extensions from a single host """
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        extension_2_id = uuid.uuid4().hex

        host = CaseStructure(case_id=host_id, attrs={'create': True})

        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ],
                attrs={'create': True}
            ),
            CaseStructure(
                case_id=extension_2_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ],
                attrs={'create': True}
            ),
        ]
        )

        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(self.domain, [host_id])
        self.assertItemsEqual(returned_cases, [extension_id, extension_2_id])

    def test_host_with_multiple_extension_types(self):
        """ Return all extensions from a single host """
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        extension_2_id = uuid.uuid4().hex

        host = CaseStructure(case_id=host_id, attrs={'create': True})

        self.factory.create_or_update_cases([
            CaseStructure(
                case_id=extension_id,
                indices=[CaseIndex(
                    host,
                    relationship=CASE_INDEX_EXTENSION,
                    identifier="host",
                )],
                attrs={
                    'case_type': 'extension',
                    'create': True,
                }
            ),
            CaseStructure(
                case_id=extension_2_id,
                indices=[CaseIndex(
                    host,
                    relationship=CASE_INDEX_EXTENSION,
                    identifier="host",
                )],
                attrs={
                    'case_type': 'extension_2',
                    'create': True,
                }
            ),
        ])

        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(
            self.domain,
            [host_id],
            case_type='extension_2',
        )
        self.assertItemsEqual(returned_cases, [extension_2_id])

    def test_extensions_from_list(self):
        """ Given a list of hosts, should return all extensions """
        host_id = uuid.uuid4().hex
        host_2_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        extension_2_id = uuid.uuid4().hex

        host = CaseStructure(case_id=host_id, attrs={'create': True})
        host_2 = CaseStructure(case_id=host_2_id, attrs={'create': True})
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_id,
                indices=[
                    CaseIndex(host, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ],
                attrs={'create': True}
            )
        )
        self.factory.create_or_update_case(
            CaseStructure(
                case_id=extension_2_id,
                indices=[
                    CaseIndex(host_2, relationship=CASE_INDEX_EXTENSION, identifier="host"),
                ],
                attrs={'create': True}
            )
        )
        returned_cases = CommCareCaseIndex.objects.get_extension_case_ids(self.domain, [host_id, host_2_id])
        self.assertItemsEqual(returned_cases, [extension_id, extension_2_id])
