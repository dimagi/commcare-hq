import uuid

from django.conf import settings
from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.case.xform import (
    get_all_extensions_to_close,
    get_extensions_to_close,
    get_ush_extension_cases_to_close,
)
from casexml.apps.phone.tests.utils import create_restore_user
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.util.test_utils import flag_enabled


@sharded
class AutoCloseExtensionsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(AutoCloseExtensionsTest, cls).setUpClass()
        delete_all_users()
        cls.domain = "domain"
        cls.project = Domain(name=cls.domain)
        cls.user = create_restore_user(cls.domain, username='name', password="changeme")
        cls.factory = CaseFactory(domain=cls.domain)
        cls.extension_ids = ['1', '2', '3']
        cls.host_id = 'host-{}'.format(uuid.uuid4().hex)
        cls.host_2_id = 'host_2-{}'.format(uuid.uuid4().hex)
        cls.parent_id = 'parent-{}'.format(uuid.uuid4().hex)

    def tearDown(self):
        if settings.USE_PARTITIONED_DATABASE:
            FormProcessorTestUtils.delete_all_cases()
            FormProcessorTestUtils.delete_all_xforms()

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        super(AutoCloseExtensionsTest, cls).tearDownClass()

    def _create_extension_chain(self):
        host = CaseStructure(case_id=self.host_id, attrs={'create': True})
        extension = CaseStructure(
            case_id=self.extension_ids[0],
            indices=[CaseIndex(
                related_structure=host,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        extension_2 = CaseStructure(
            case_id=self.extension_ids[1],
            indices=[CaseIndex(
                related_structure=extension,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        extension_3 = CaseStructure(
            case_id=self.extension_ids[2],
            indices=[CaseIndex(
                related_structure=extension_2,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        return self.factory.create_or_update_cases([extension_3])

    def _create_extension_loop(self):
        extension_3 = CaseStructure(case_id=self.extension_ids[2])
        host = CaseStructure(
            case_id=self.host_id,
            indices=[CaseIndex(
                related_structure=extension_3,
                relationship="extension",
            )],
        )
        return self.factory.create_or_update_cases([host])

    def _create_host_is_subcase_chain(self):
        parent = CaseStructure(case_id=self.parent_id, attrs={'create': True})
        host = CaseStructure(
            case_id=self.host_id,
            indices=[CaseIndex(
                related_structure=parent,
                relationship="child",
            )],
            attrs={'create': True}
        )
        extension = CaseStructure(
            case_id=self.extension_ids[0],
            indices=[CaseIndex(
                related_structure=host,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        extension_2 = CaseStructure(
            case_id=self.extension_ids[1],
            indices=[CaseIndex(
                related_structure=extension,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        return self.factory.create_or_update_cases([extension_2])

    def _create_two_host_extension(self):
        host = CaseStructure(case_id=self.host_id, attrs={'create': True})
        host_2 = CaseStructure(case_id=self.host_2_id, attrs={'create': True})
        extension = CaseStructure(
            case_id=self.extension_ids[0],
            indices=[
                CaseIndex(
                    identifier='host',
                    related_structure=host,
                    relationship="extension",
                ),
                CaseIndex(
                    identifier='host_2',
                    related_structure=host_2,
                    relationship="extension",
                ),
            ],
            attrs={'create': True}
        )
        return self.factory.create_or_update_cases([extension])

    def test_get_extension_chain_simple(self):
        host = CaseStructure(case_id=self.host_id, attrs={'create': True})
        extension = CaseStructure(
            case_id=self.extension_ids[0],
            indices=[CaseIndex(
                related_structure=host,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        self.factory.create_or_update_cases([extension])
        self.assertEqual(
            set(self.extension_ids[0]),
            CommCareCaseIndex.objects.get_extension_chain(self.domain, [self.host_id])
        )

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    @flag_enabled('USH_DONT_CLOSE_PATIENT_EXTENSIONS')
    def test_get_ush_custom_extension_chain(self):
        # test USH specific tree of where only extension(2) should be included
        #       patient (host)
        #     /        \
        #  contact(id=1)   extension(id=2)
        #   /
        # extension(id=3)
        host = CaseStructure(case_id=self.host_id, attrs={'create': True, 'case_type': 'patient'})
        contact_extension = CaseStructure(
            case_id=self.extension_ids[0],
            indices=[CaseIndex(
                related_structure=host,
                relationship="extension",
            )],
            attrs={'create': True, 'case_type': 'contact'}
        )
        extensions_1 = CaseStructure(
            case_id=self.extension_ids[1],
            indices=[CaseIndex(
                related_structure=host,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        ext_of_contact = CaseStructure(
            case_id=self.extension_ids[2],
            indices=[CaseIndex(
                related_structure=contact_extension,
                relationship="extension",
            )],
            attrs={'create': True}
        )
        created_cases = self.factory.create_or_update_cases([ext_of_contact])
        self.factory.create_or_update_cases([extensions_1])
        created_cases[-1].closed = True
        self.assertEqual(
            set(self.extension_ids),
            get_extensions_to_close(self.domain, [created_cases[-1]])
        )
        # contact and its extensions shouldn't be included in USH case
        self.assertEqual(
            {self.extension_ids[1]},
            get_ush_extension_cases_to_close(self.domain, [created_cases[-1]])
        )

    def test_get_extension_chain_multiple(self):
        created_cases = self._create_extension_chain()
        self.assertEqual(
            set(self.extension_ids),
            CommCareCaseIndex.objects.get_extension_chain(self.domain, [created_cases[-1].case_id])
        )

    def test_get_extension_chain_circular_ref(self):
        """If there is a circular reference, this should not hang forever
        """
        self._create_extension_chain()
        self._create_extension_loop()

        self.assertEqual(
            set([self.host_id] + self.extension_ids),
            CommCareCaseIndex.objects.get_extension_chain(self.domain, [self.extension_ids[2]])
        )

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_get_extension_to_close(self):
        """should return empty if case is not a host, otherwise should return full chain"""
        created_cases = self._create_extension_chain()
        # host open, should be empty
        no_cases = get_all_extensions_to_close(self.domain, [created_cases[-1]])
        self.assertEqual(set(), no_cases)

        # don't actually close the cases otherwise they will get excluded
        created_cases[-1].closed = True

        # top level host closed, should get full chain
        full_chain = get_all_extensions_to_close(self.domain, [created_cases[-1]])
        self.assertEqual(set(self.extension_ids), full_chain)

        # extension (also a host), should get it's chain
        created_cases[2].closed = True
        no_cases = get_all_extensions_to_close(self.domain, [created_cases[2]])
        self.assertEqual(set(self.extension_ids[1:3]), no_cases)

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_get_extension_to_close_child_host(self):
        """should still return extension chain if outgoing index is a child index"""
        created_cases = self._create_host_is_subcase_chain()
        # host open, should be empty
        no_cases = get_all_extensions_to_close(self.domain, [created_cases[-1]])
        self.assertEqual(set(), no_cases)

        # close parent, shouldn't get extensions
        # don't actually close the cases otherwise they will get excluded
        created_cases[-1].closed = True
        no_cases = get_all_extensions_to_close(self.domain, [created_cases[-1]])
        self.assertEqual(set(), no_cases)

        # close host that is also a child
        created_cases[-2].closed = True
        full_chain = get_all_extensions_to_close(self.domain, [created_cases[-2]])
        self.assertEqual(set(self.extension_ids[0:2]), full_chain)

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_close_cases_host(self):
        """Closing a host should close all the extensions"""
        self._create_extension_chain()
        cases = CommCareCase.objects.get_cases(self.extension_ids, self.domain)
        self.assertFalse(cases[0].closed)
        self.assertFalse(cases[1].closed)
        self.assertFalse(cases[2].closed)

        self.factory.create_or_update_case(CaseStructure(
            case_id=self.extension_ids[1],
            attrs={'close': True}
        ))
        cases = {
            case.case_id: case.closed
            for case in CommCareCase.objects.get_cases([self.host_id] + self.extension_ids, self.domain)
        }
        self.assertFalse(cases[self.host_id])
        self.assertFalse(cases[self.extension_ids[0]])
        self.assertTrue(cases[self.extension_ids[1]])
        self.assertTrue(cases[self.extension_ids[2]])

        self.factory.create_or_update_case(CaseStructure(
            case_id=self.host_id,
            attrs={'close': True}
        ))
        cases = {
            case.case_id: case
            for case in CommCareCase.objects.get_cases([self.host_id] + self.extension_ids, self.domain)
        }
        self.assertTrue(cases[self.host_id].closed)
        self.assertTrue(cases[self.extension_ids[0]].closed)
        self.assertTrue(cases[self.extension_ids[1]].closed)
        self.assertTrue(cases[self.extension_ids[2]].closed)

        self.assertEqual(1, len(cases[self.host_id].get_closing_transactions()))
        self.assertEqual(1, len(cases[self.extension_ids[0]].get_closing_transactions()))
        self.assertEqual(1, len(cases[self.extension_ids[1]].get_closing_transactions()))
        self.assertEqual(1, len(cases[self.extension_ids[2]].get_closing_transactions()))

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_closing_one_host_closes_extension(self):
        """Closing any host should close a shared extension."""
        self._create_two_host_extension()
        cases = CommCareCase.objects.get_cases(
            [self.host_id, self.host_2_id, self.extension_ids[0]],
            self.domain,
        )
        self.assertFalse(cases[0].closed)
        self.assertFalse(cases[1].closed)
        self.assertFalse(cases[2].closed)

        self.factory.create_or_update_case(CaseStructure(
            case_id=self.host_id,
            attrs={'close': True}
        ))

        cases = {
            case.case_id: case
            for case in CommCareCase.objects.get_cases(
                [self.host_id, self.host_2_id, self.extension_ids[0]],
                self.domain,
            )
        }
        self.assertTrue(cases[self.host_id].closed)
        self.assertFalse(cases[self.host_2_id].closed)
        self.assertTrue(cases[self.extension_ids[0]].closed)

    @flag_enabled('EXTENSION_CASES_SYNC_ENABLED')
    def test_close_cases_child(self):
        """Closing a host that is also a child should close all the extensions"""
        self._create_host_is_subcase_chain()
        cases = {
            case.case_id: case.closed
            for case in CommCareCase.objects.get_cases([self.host_id] + self.extension_ids, self.domain)
        }
        self.assertFalse(cases[self.host_id])
        self.assertFalse(cases[self.extension_ids[0]])
        self.assertFalse(cases[self.extension_ids[1]])

        self.factory.create_or_update_case(CaseStructure(
            case_id=self.host_id,
            attrs={'close': True}
        ))
        cases = {
            case.case_id: case
            for case in CommCareCase.objects.get_cases(
                [self.parent_id, self.host_id] + self.extension_ids, self.domain)
        }
        self.assertFalse(cases[self.parent_id].closed)
        self.assertTrue(cases[self.host_id].closed)
        self.assertTrue(cases[self.extension_ids[0]].closed)
        self.assertTrue(cases[self.extension_ids[1]].closed)

        self.assertEqual(1, len(cases[self.host_id].get_closing_transactions()))
        self.assertEqual(1, len(cases[self.extension_ids[0]].get_closing_transactions()))
        self.assertEqual(1, len(cases[self.extension_ids[1]].get_closing_transactions()))
