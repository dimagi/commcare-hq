from datetime import datetime

from django.test import TestCase

from dateutil.relativedelta import relativedelta
from mock import patch

from casexml.apps.case.mock import CaseFactory
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.data_interfaces.deduplication import find_duplicate_cases
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDeduplicationActionDefinition,
    CaseDeduplicationMatchTypeChoices,
    CaseDuplicate,
)
from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import create_test_case, trap_extra_setup


class CaseRuleCriteriaTest(TestCase):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)

        cls.domain = 'case-dedupe-test'
        cls.case_type = 'adult'

        cls.rule = AutomaticUpdateRule.objects.create(
            domain=cls.domain,
            name='test',
            case_type=cls.case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )

    @classmethod
    def tearDownClass(cls, *args, **kwargs):
        cls.rule.delete()
        super().tearDownClass()

    def test_new_cases_only(self):
        now = datetime.utcnow()
        with create_test_case(self.domain, self.case_type, "case a", drop_signals=False) as case:
            self.assertTrue(self.rule.criteria_match(case, now))
            self.rule.last_run = now + relativedelta(minutes=5)
            self.assertFalse(self.rule.criteria_match(case, now))


@es_test
class FindingDuplicatesTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.es = get_es_new()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(cls.es, CASE_SEARCH_INDEX_INFO)

        cls.domain = 'naboo'
        cls.factory = CaseFactory(cls.domain)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super().tearDownClass()

    def _prime_es_index(self, cases):
        for case in cases:
            send_to_elasticsearch('case_search', transform_case_for_elasticsearch(case.to_json()))
        self.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    def test_find_simple_duplicates(self):
        cases = []
        for (case_name, dob) in [
            ("Padme Amidala", "1901-05-01"),
            ("Padme Amidala", "1901-05-01"),
            ("Anakin Skywalker", "1977-03-25"),
            ("Darth Vadar", "1977-03-25"),
        ]:
            cases.append(self.factory.create_case(case_name=case_name, update={'dob': dob}))

        self._prime_es_index(cases)

        # Padme is clearly a duplicate
        self.assertItemsEqual([cases[0].case_id, cases[1].case_id], [
            case.case_id for case in find_duplicate_cases(self.domain, cases[0], ["name", "dob"])
        ])

        # Spoiler alert, Anakin is Vadar!
        self.assertItemsEqual([cases[2].case_id, cases[3].case_id],
                              [case.case_id for case in find_duplicate_cases(self.domain, cases[2], ["dob"])])

        # When you go to the dark side, you are no longer the same jedi.
        self.assertNotIn(
            cases[3].case_id, [case.case_id for case in find_duplicate_cases(self.domain, cases[2], ["name"])]
        )

    def test_duplicates_different_case_types(self):
        """Should not return duplicates
        """

    def test_find_closed_duplicates(self):
        """closed duplicates should or shouldn't be found based on input
        """

    def test_find_duplicates_or_rule(self):
        """find duplicates where any case properties match
        """


class CaseDeduplicationActionTest(TestCase):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)

        cls.domain = 'case-dedupe-test'
        cls.case_type = 'adult'
        cls.factory = CaseFactory(cls.domain)
        cls.accessor = CaseAccessors(cls.domain)

        cls.rule = AutomaticUpdateRule.objects.create(
            domain=cls.domain,
            name='test',
            case_type=cls.case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        _, cls.action = cls.rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["name", "age"],
        )

        cls.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='is_potential_duplicate',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='yes',
            )
        ])
        cls.action.save()

    @classmethod
    def tearDownClass(cls, *args, **kwargs):
        cls.rule.hard_delete()
        super().tearDownClass()

    def tearDown(self):
        CaseDuplicate.objects.all().delete()

    def _create_cases(self):
        case_1 = self.factory.create_case(case_name='name', update={"age": 2})
        case_2 = self.factory.create_case(case_name='name', update={"age": 2})

        return [case_1, case_2]

    @patch("corehq.apps.data_interfaces.models.find_duplicate_cases")
    def test_updates_a_duplicate(self, find_duplicates_mock):
        case_1, case_2 = self._create_cases()
        find_duplicates_mock.return_value = [case_1, case_2]

        self.rule.run_actions_when_case_matches(case_1)

        case_1 = self.accessor.get_case(case_1.case_id)
        case_2 = self.accessor.get_case(case_2.case_id)

        self.assertEqual(case_1.get_case_property('is_potential_duplicate'), 'yes')
        self.assertEqual(case_2.get_case_property('is_potential_duplicate'), 'yes')

    @patch("corehq.apps.data_interfaces.models.find_duplicate_cases")
    def test_stores_all_duplicates(self, find_duplicates_mock):
        """When it finds duplicates, store them in the CaseDuplicate model
        """
        case_1, case_2 = self._create_cases()
        find_duplicates_mock.return_value = [case_1, case_2]

        self.rule.run_actions_when_case_matches(case_1)

        duplicates = list(
            CaseDuplicate.objects.filter(action=self.action).all()
        )
        self.assertItemsEqual([duplicate.case_id for duplicate in duplicates], [case_1.case_id, case_2.case_id])

        self.assertEqual(duplicates[0].potential_duplicates.count(), 1)
        self.assertEqual(duplicates[0].potential_duplicates.first().case_id, case_1.case_id)

    @patch("corehq.apps.data_interfaces.models.find_duplicate_cases")
    def test_case_no_longer_duplicate(self, find_duplicates_mock):
        """When the case is no longer a duplicate, it should be removed from the CaseDuplicate model
        """
        case_1, case_2 = self._create_cases()

        find_duplicates_mock.return_value = [case_1, case_2]
        self.rule.run_actions_when_case_matches(case_1)
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), 2)

        find_duplicates_mock.return_value = [case_1]
        self.rule.run_actions_when_case_matches(case_1)

        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), 0)

    @patch("corehq.apps.data_interfaces.models.find_duplicate_cases")
    def test_case_already_duplicate(self, find_duplicates_mock):
        """What happens when a case is already in the list
        """
        case_1, case_2 = self._create_cases()

        find_duplicates_mock.return_value = [case_1, case_2]
        self.rule.run_actions_when_case_matches(case_1)
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), 2)

        # No extra case duplicates should be created
        self.rule.run_actions_when_case_matches(case_1)
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), 2)

    @es_test
    def test_integration_test(self):
        """Don't mock the find_duplicate_ids response to make sure it works
        """

    def test_update_case_no_longer_duplicate(self):
        """What happens if the case update deduplicates the case?
        """
        # If "ALL" & update is one of the target properties, we know to remove it
        # If "ANY", do we need to search again?
        # Do we allow this? (could block on updating target properties, for example)

    def test_last_case_changed_not_duplicate(self):
        """Case A and Case B are duplicates of each other. Case A is changed so it is
        no longer a duplicate, Case B should be removed from the list of
        duplicates.
        """
