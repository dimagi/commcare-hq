from datetime import datetime
from itertools import chain

from django.test import TestCase, override_settings

from dateutil.relativedelta import relativedelta
from faker import Faker
from mock import patch

from casexml.apps.case.mock import CaseFactory
from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.topics import get_multi_topic_offset
from corehq.apps.data_interfaces.deduplication import find_duplicate_case_ids
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDeduplicationActionDefinition,
    CaseDeduplicationMatchTypeChoices,
    CaseDuplicate,
)
from corehq.apps.data_interfaces.pillow import CaseDeduplicationProcessor
from corehq.apps.es.tests.utils import es_test
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case_search import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX_INFO
from corehq.pillows.xform import get_xform_pillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import (
    create_test_case,
    flag_enabled,
    trap_extra_setup,
)


class CaseRuleCriteriaTest(TestCase):

    @classmethod
    def setUpTestData(cls, *args, **kwargs):

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

    def test_new_cases_only(self):
        now = datetime.utcnow()
        with create_test_case(self.domain, self.case_type, "case a", drop_signals=False) as case:
            self.assertTrue(self.rule.criteria_match(case, now))
            self.rule.last_run = now + relativedelta(minutes=5)
            self.assertFalse(self.rule.criteria_match(case, now))


@es_test
class FindingDuplicatesTest(TestCase):

    def setUp(self):
        super().setUp()

        self.es = get_es_new()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(self.es, CASE_SEARCH_INDEX_INFO)

        self.domain = 'naboo'
        self.factory = CaseFactory(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        ensure_index_deleted(CASE_SEARCH_INDEX_INFO.index)
        super().tearDown()

    def _prime_es_index(self, cases):
        for case in cases:
            send_to_elasticsearch('case_search', transform_case_for_elasticsearch(case.to_json()))
        self.es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

    def test_find_simple_duplicates(self):
        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Padme Amidala", "1901-05-01"),
                ("Padme Amidala", "1901-05-01"),
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
            ]
        ]

        self._prime_es_index(cases)

        # Padme is clearly a duplicate
        self.assertItemsEqual([cases[0].case_id, cases[1].case_id],
                              find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"]))

        # Spoiler alert, Anakin is Vadar!
        self.assertItemsEqual([cases[2].case_id, cases[3].case_id],
                              find_duplicate_case_ids(self.domain, cases[2], ["dob"]))

        # When you go to the dark side, you are no longer the same jedi.
        self.assertNotIn(cases[3].case_id, find_duplicate_case_ids(self.domain, cases[2], ["name"]))

    def test_duplicates_different_case_types(self):
        """Should not return duplicates
        """
        cases = [
            self.factory.create_case(case_name=case_name, case_type=case_type, update={'dob': dob})
            for (case_name, dob, case_type) in [
                ("Padme Amidala", "1901-05-01", "Ashla"),
                ("Padme Amidala", "1901-05-01", "Light"),
                ("Anakin Skywalker", "1977-03-25", "Dark"),
                ("Darth Vadar", "1977-03-25", "Dark"),
            ]
        ]

        self._prime_es_index(cases)

        # Padme cases are of different case types
        self.assertNotIn(
            cases[1].case_id,
            find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"]),
        )

        # Anakin / Vadar are still the same
        self.assertIn(cases[3].case_id, find_duplicate_case_ids(self.domain, cases[2], ["dob"]))

    def test_find_closed_duplicates(self):
        """closed duplicates should or shouldn't be found based on input
        """

        cases = [
            self.factory.create_case(case_name=case_name, close=closed, update={'dob': dob})
            for (case_name, dob, closed) in [
                ("Padme Amidala", "1901-05-01", False),
                ("Padme Amidala", "1901-05-01", True),
                ("Anakin Skywalker", "1977-03-25", False),
                ("Darth Vadar", "1977-03-25", True),
            ]
        ]

        self._prime_es_index(cases)

        # Even though the Padme case is closed, it should still be flagged as a duplicate
        self.assertItemsEqual([cases[0].case_id, cases[1].case_id],
                              find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"], include_closed=True))

        # The Vadar case is closed, so shouldn't be returned
        self.assertItemsEqual([cases[2].case_id],
                              find_duplicate_case_ids(self.domain, cases[2], ["dob"], include_closed=False))

    def test_find_duplicates_any_rule(self):
        """find duplicates where any case properties match
        """
        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Padme Amidala", "1901-05-01"),
                ("Padme Amidala", "1901-05-01"),
                ("Padme Amidala", "1901-05-02"),
                ("Padme Naberrie", "1901-05-01"),
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
            ]
        ]

        self._prime_es_index(cases)

        self.assertItemsEqual([cases[0].case_id, cases[1].case_id, cases[2].case_id, cases[3].case_id],
                              find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"], match_type="ANY"))

        self.assertItemsEqual([cases[4].case_id, cases[5].case_id],
                              find_duplicate_case_ids(self.domain, cases[4], ["name", "dob"], match_type="ANY"))


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
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def _create_cases(self, num_cases=5):
        faker = Faker()
        duplicate_name = "George Simon Esq."
        duplicate_age = 12

        duplicates = [
            self.factory.create_case(
                case_name=duplicate_name, case_type=self.case_type, update={"age": duplicate_age}
            ) for _ in range(num_cases)
        ]
        uniques = [
            self.factory.create_case(
                case_name=faker.name(), case_type=self.case_type, update={"age": faker.random_int(1, 100)}
            ) for _ in range(num_cases)
        ]

        return duplicates, uniques

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_updates_a_duplicate(self, find_duplicates_mock):
        """Ensure that all duplicates are updated by the rule
        """

        duplicates, uniques = self._create_cases()
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        for duplicate_case in duplicates:
            self.assertEqual(
                self.accessor.get_case(duplicate_case.case_id).get_case_property('is_potential_duplicate'), 'yes'
            )

        for unique_case in uniques:
            self.assertIsNone(
                self.accessor.get_case(unique_case.case_id).get_case_property('is_potential_duplicate'),
            )

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_updates_a_duplicate_only_once(self, find_duplicates_mock):
        """Ensure that all duplicates are only updated once per change
        """

        duplicates, uniques = self._create_cases()
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])
        self.rule.run_actions_when_case_matches(duplicates[1])

        # duplicates[1] should already have been updated by the first action.
        # It should only have two transactions (create and the initial
        # duplicate update). This prevents a situation where there are many
        # duplicates of the same case that get updated N times
        form_transactions = CaseAccessors(self.domain).get_case(duplicates[1].case_id).get_form_transactions()
        self.assertEqual(2, len(form_transactions))

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_unique_not_updated(self, find_duplicates_mock):
        """Ensure that new unique cases are not updated
        """

        duplicates, uniques = self._create_cases(1)
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        for duplicate_case in duplicates:
            self.assertIsNone(
                self.accessor.get_case(duplicate_case.case_id).get_case_property('is_potential_duplicate'),
            )

        for unique_case in uniques:
            self.assertIsNone(
                self.accessor.get_case(unique_case.case_id).get_case_property('is_potential_duplicate'),
            )

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_stores_all_duplicates(self, find_duplicates_mock):
        """When it finds duplicates, store them in the CaseDuplicate model
        """
        duplicates, uniques = self._create_cases()
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        # New CaseDuplicate objects should be created for all the duplicate cases
        self.assertItemsEqual(
            list(CaseDuplicate.objects.filter(action=self.action).all().values_list('case_id', flat=True)),
            [duplicate.case_id for duplicate in duplicates]
        )

        # The potential_duplicates list for the searched case is the set of all duplicate cases
        self._assert_potential_duplicates(duplicates[0].case_id, duplicates)

    def _assert_potential_duplicates(self, case_id, duplicates):
        case_duplicate_searched_case = CaseDuplicate.objects.get(case_id=case_id)
        self.assertCountEqual(
            list(case_duplicate_searched_case.potential_duplicates.all().values_list('case_id', flat=True)),
            [duplicate.case_id for duplicate in duplicates if duplicate.case_id != case_id]
        )

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_stores_all_duplicates_pillow_behind(self, find_duplicates_mock):
        """If the case search pillow doesn't contain the case we're searching for, we
        should still be able to store all updates

        """
        duplicates, uniques = self._create_cases()

        # The searched case isn't returned by the elasticsearch query
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates][1:]

        self.rule.run_actions_when_case_matches(duplicates[0])

        # But there should be a CaseDuplicate object created for the searched case anyway
        self.assertItemsEqual(
            list(CaseDuplicate.objects.filter(action=self.action).all().values_list('case_id', flat=True)),
            [duplicate.case_id for duplicate in duplicates]
        )

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_case_no_longer_duplicate(self, find_duplicates_mock):
        """When the case is no longer a duplicate, it should be removed from the CaseDuplicate model
        """
        duplicates, uniques = self._create_cases()
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        # The first case is no longer a duplicate
        find_duplicates_mock.return_value = [duplicates[0].case_id]
        self.rule.run_actions_when_case_matches(duplicates[0])

        # All the other cases are now unique too
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), 0)

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_case_already_marked_duplicate(self, find_duplicates_mock):
        """What happens when a case is already in the list
        """
        num_duplicates = 5
        duplicates, uniques = self._create_cases(num_duplicates)
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), num_duplicates)
        initial_case_duplicate_id = CaseDuplicate.objects.get(case_id=duplicates[0].case_id).id

        # No extra case duplicates should be created, and the id should remain the same
        self.rule.run_actions_when_case_matches(duplicates[0])
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), num_duplicates)
        self._assert_potential_duplicates(duplicates[0].case_id, duplicates)
        self.assertEqual(initial_case_duplicate_id, CaseDuplicate.objects.get(case_id=duplicates[0].case_id).id)

        # Updating or submitting the second duplicate case we should not
        # create new `CaseDuplicate`, but this should update the
        # potential_duplicates for that case
        self.rule.run_actions_when_case_matches(duplicates[1])
        self.assertEqual(CaseDuplicate.objects.filter(action=self.action).count(), num_duplicates)
        self._assert_potential_duplicates(duplicates[1].case_id, duplicates)

    @es_test
    def test_integration_test(self):
        """Don't mock the find_duplicate_ids response to make sure it works
        """
        es = get_es_new()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(es, CASE_SEARCH_INDEX_INFO)
        self.addCleanup(ensure_index_deleted, CASE_SEARCH_INDEX_INFO.index)

        duplicates, uniques = self._create_cases()

        for case in chain(duplicates, uniques):
            send_to_elasticsearch('case_search', transform_case_for_elasticsearch(case.to_json()))
        es.indices.refresh(CASE_SEARCH_INDEX_INFO.index)

        self.rule.run_actions_when_case_matches(duplicates[0])

        self._assert_potential_duplicates(duplicates[0].case_id, duplicates)


@override_settings(RUN_UNKNOWN_USER_PILLOW=False)
@override_settings(RUN_FORM_META_PILLOW=False)
@flag_enabled('CASE_DEDUPE')
class DeduplicationPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'naboo'
        cls.case_type = 'people'
        cls.factory = CaseFactory(cls.domain)
        cls.pillow = get_xform_pillow(skip_ucr=True)

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
            case_properties=["case_name", "age"],
        )
        cls.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='age',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='5',
            ),
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='case_name',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='Herman Miller',
            )
        ])
        cls.action.save()
        AutomaticUpdateRule.clear_caches(cls.domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

    @patch("corehq.apps.data_interfaces.models.find_duplicate_case_ids")
    def test_pillow_processes_changes(self, find_duplicate_cases_mock):
        kafka_sec = get_multi_topic_offset([topics.FORM, topics.FORM_SQL])

        case1 = self.factory.create_case(case_name="foo", case_type=self.case_type, update={"age": 2})
        case2 = self.factory.create_case(case_name="foo", case_type=self.case_type, update={"age": 2})
        find_duplicate_cases_mock.return_value = [case1.case_id, case2.case_id]

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

        new_kafka_sec = get_multi_topic_offset([topics.FORM, topics.FORM_SQL])
        self.pillow.process_changes(since=kafka_sec, forever=False)

        self._assert_case_duplicate_pair(case1.case_id, [case2.case_id])
        self._assert_case_duplicate_pair(case2.case_id, [case1.case_id])
        self.assertEqual(CaseDuplicate.objects.count(), 2)
        self.assertEqual(CaseAccessors(self.domain).get_case(case1.case_id).get_case_property('age'), '5')
        self.assertEqual(CaseAccessors(self.domain).get_case(case1.case_id).name, 'Herman Miller')

        # The new changes present should not be processed by the pillow
        # processor, since they were updates from a duplicate action.
        with patch.object(CaseDeduplicationProcessor, '_process_case_update') as p:
            self.pillow.process_changes(since=new_kafka_sec, forever=False)
            p.assert_not_called()

    def _assert_case_duplicate_pair(self, case_id_to_check, expected_duplicates):
        potential_duplicates = list(
            CaseDuplicate.objects
            .get(case_id=case_id_to_check)
            .potential_duplicates.values_list('case_id', flat=True)
        )
        self.assertItemsEqual(potential_duplicates, expected_duplicates)
