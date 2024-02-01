from datetime import datetime
from itertools import chain
from unittest.mock import patch

from django.test import TestCase, override_settings

from faker import Faker

from casexml.apps.case.mock import CaseFactory

from corehq.apps.change_feed import topics
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.data_interfaces.deduplication import (
    _get_es_filtered_case_query,
    backfill_deduplicate_rule,
    find_duplicate_case_ids,
    case_exists_in_es
)
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDeduplicationActionDefinition,
    CaseDeduplicationMatchTypeChoices,
    CaseDuplicateNew,
    CaseRuleCriteria,
    LocationFilterDefinition,
    MatchPropertyDefinition,
)
from corehq.apps.data_interfaces.utils import run_rules_for_case
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.hqcase.case_helper import CaseCopier
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.tasks import tag_cases_as_deleted_and_remove_indices
from corehq.form_processor.models import CommCareCase
from corehq.pillows.case import get_case_pillow
from corehq.util.test_utils import flag_enabled, set_parent_case
from corehq.apps.hqcase.utils import resave_case


@es_test(requires=[case_search_adapter])
@es_test(requires=[user_adapter], setup_class=True)
class FindingDuplicatesQueryTest(TestCase):
    def setUp(self):
        super().setUp()
        self.domain = 'naboo'
        self.factory = CaseFactory(self.domain)

    def _prime_es_index(self, cases):
        case_search_adapter.bulk_index(cases, refresh=True)

    def test_without_filters(self):
        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Pixel Brain", ""),
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
            ]
        ]
        self._prime_es_index(cases)

        query = _get_es_filtered_case_query(self.domain, cases[0])
        retrieved_cases = query.run().hits

        self.assertEqual(len(retrieved_cases), len(cases))

    def test_with_location_filter(self):
        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
                ("Wannabe Anakin Skywalker", "1977-03-25"),
                ("Wannabe Darth Vadar", "1977-03-25"),
            ]
        ]

        rule = self.create_rule('test rule', cases[0].type)
        # Create a filter criteria of cases to consider
        definition = LocationFilterDefinition.objects.create(
            location_id='mustafar_id',
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        location_id = 'mustafar_id'

        # Only assign location id to first 2 cases, since we want only those two cases to be considered
        cases[0].owner_id = location_id
        cases[1].owner_id = location_id

        self._prime_es_index(cases)

        query = _get_es_filtered_case_query(self.domain, cases[0], rule.memoized_criteria)
        retrieved_cases = query.run().hits

        self.assertEqual(len(retrieved_cases), 2)
        self.assertTrue(retrieved_cases[0]['owner_id'] == location_id)
        self.assertTrue(retrieved_cases[1]['owner_id'] == location_id)

    def test_with_case_properties_filter_match_equal(self):
        match_type = MatchPropertyDefinition.MATCH_EQUAL

        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
                ("Anakin Skywalker", "1977-03-25"),
                ("Wannabe Darth Vadar", "1977-03-25"),
            ]
        ]
        self._prime_es_index(cases)

        rule = self.create_rule('test rule', cases[0].type)
        # Create a filter criteria of cases to consider
        definition_property_value = 'Anakin Skywalker'
        definition = MatchPropertyDefinition.objects.create(
            property_name='name',
            property_value=definition_property_value,
            match_type=match_type,
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        query = _get_es_filtered_case_query(self.domain, cases[0], rule.memoized_criteria)
        retrieved_cases = query.run().hits

        self.assertEqual(len(retrieved_cases), 2)

        for case in retrieved_cases:
            self.assertEqual(case['name'], definition_property_value)

    def test_with_case_properties_filter_match_not_equal(self):
        match_type = MatchPropertyDefinition.MATCH_NOT_EQUAL

        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
                ("Anakin Skywalker", "1977-03-25"),
                ("Wannabe Darth Vadar", "1977-03-25"),
            ]
        ]
        self._prime_es_index(cases)

        rule = self.create_rule('test rule', cases[0].type)
        # Create a filter criteria of cases to consider
        definition = MatchPropertyDefinition.objects.create(
            property_name='name',
            property_value='Wannabe Darth Vadar',
            match_type=match_type,
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        query = _get_es_filtered_case_query(self.domain, cases[0], rule.memoized_criteria)
        retrieved_cases = query.run().hits

        self.assertEqual(len(retrieved_cases), 3)
        for case in retrieved_cases:
            self.assertNotEqual(case['name'], 'Wannabe Darth Vadar')

    def test_with_case_properties_filter_match_has_value(self):
        match_type = MatchPropertyDefinition.MATCH_HAS_VALUE

        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Anakin Skywalker", ""),
                ("Darth Vadar", "1977-03-25"),
            ]
        ]
        cases.append(self.factory.create_case(case_name='Chewbacca'))

        self._prime_es_index(cases)

        rule = self.create_rule('test rule', cases[0].type)
        # Create a filter criteria of cases to consider
        definition = MatchPropertyDefinition.objects.create(
            property_name='dob',
            match_type=match_type,
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        query = _get_es_filtered_case_query(self.domain, cases[0], rule.memoized_criteria)
        retrieved_cases = query.run().hits

        self.assertEqual(len(retrieved_cases), 1)

        case_properties = retrieved_cases[0]['case_properties']
        dob = next((prop['value'] for prop in case_properties if prop['key'] == 'dob'))
        self.assertEqual(dob, "1977-03-25")

    def test_with_case_properties_filter_match_has_no_value(self):
        match_type = MatchPropertyDefinition.MATCH_HAS_NO_VALUE

        cases = [
            self.factory.create_case(case_name=case_name, update={'age': age}) for (case_name, age) in [
                ("Anakin Skywalker", ""),
                ("Darth Vadar", "41"),
                ("Wannabe Darth Vadar", "14"),
            ]
        ]
        cases.append(self.factory.create_case(case_name='Chewbacca', update={'needs_to_see_hairdresser': 'yes'}))
        self._prime_es_index(cases)

        rule = self.create_rule('test rule', cases[0].type)
        # Create a filter criteria of cases to consider
        definition = MatchPropertyDefinition.objects.create(
            property_name='age',
            match_type=match_type,
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        query = _get_es_filtered_case_query(self.domain, cases[0], rule.memoized_criteria)
        retrieved_cases = query.run().hits

        self.assertEqual(len(retrieved_cases), 2)
        retrieved_cases_names = [case['name'] for case in retrieved_cases]
        self.assertIn('Anakin Skywalker', retrieved_cases_names)
        self.assertIn('Chewbacca', retrieved_cases_names)

    def create_rule(self, rule_name, case_type):
        return AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name=rule_name,
            case_type=case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )


@es_test(requires=[case_search_adapter])
class EnsureCaseExistsTest(TestCase):
    def setUp(self):
        super().setUp()
        self.domain = 'naboo'
        self.factory = CaseFactory(self.domain)

    def _prime_es_index(self, cases):
        case_search_adapter.bulk_index(cases, refresh=True)

    def test_when_case_is_not_in_elasticsearch_returns_false(self):
        case = self._create_case()
        self._prime_es_index([])
        self.assertFalse(case_exists_in_es(self.domain, case, ['case_name']))

    def test_when_case_exists_returns_true(self):
        case = self._create_case()
        self._prime_es_index([case])
        self.assertTrue(case_exists_in_es(self.domain, case, ['case_name']))

    def test_when_case_parameters_do_not_match_returns_false(self):
        case = self._create_case(name='Anakin Skywalker')
        updated_case = self.factory.update_case(case.case_id, update={'case_name': 'Darth Vader'})
        self._prime_es_index([case])

        self.assertFalse(case_exists_in_es(self.domain, updated_case, ['case_name']))

    def test_case_requires_matching_on_case_id(self):
        cases = [self._create_case() for i in range(2)]

        self._prime_es_index([cases[0]])
        self.assertFalse(case_exists_in_es(self.domain, cases[1], ['case_name']))

    def test_when_case_parameters_match_returns_true(self):
        case = self._create_case(name='Anakin Skywalker')
        updated_case = self.factory.update_case(case.case_id, update={'age': 27})
        self._prime_es_index([case])

        self.assertTrue(case_exists_in_es(self.domain, updated_case, ['case_name']))

    def _create_case(self, name='Anakin Skywalker'):
        return self.factory.create_case(case_name=name, update={})


@es_test(requires=[case_search_adapter])
class FindingDuplicatesTest(TestCase):

    def setUp(self):
        super().setUp()

        self.domain = 'naboo'
        self.factory = CaseFactory(self.domain)

    def _prime_es_index(self, cases):
        case_search_adapter.bulk_index(cases, refresh=True)

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

    @patch("corehq.apps.data_interfaces.deduplication.DUPLICATE_LIMIT", 2)
    def test_find_maximum_number_of_results(self):
        cases = [
            self.factory.create_case(case_name='Padme Amidala', update={'dob': '1901-05-01'}) for i in range(3)
        ]

        self._prime_es_index(cases)

        results = find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"])
        self.assertEqual(len(results), 2)

    def test_limit_is_respected(self):
        cases = [
            self.factory.create_case(case_name='Padme Amidala', update={'dob': '1901-05-01'}) for i in range(3)
        ]

        self._prime_es_index(cases)

        results = find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"], limit=2)
        self.assertEqual(len(results), 2)

    @patch("corehq.apps.data_interfaces.deduplication.DUPLICATE_LIMIT", 2)
    def test_limit_overrides_default_maximum(self):
        cases = [
            self.factory.create_case(case_name='Padme Amidala', update={'dob': '1901-05-01'}) for i in range(4)
        ]

        self._prime_es_index(cases)
        results = find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"], limit=3)
        self.assertEqual(len(results), 3)

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

    def test_find_duplicates_blank_case_properties(self):
        """cases with blank properties shouldn't match
        """
        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Padme Amidala", ""),
                ("Padme Naberrie", ""),
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
            ]
        ]

        self._prime_es_index(cases)

        # An inexistent property shouldn't match any cases
        self.assertItemsEqual([
            cases[0].case_id
        ], find_duplicate_case_ids(self.domain, cases[0], ["random_property"], match_type="ANY"))

        # A blank property shouldn't match any cases, even though there are
        # other cases where that property is blank
        self.assertItemsEqual([cases[0].case_id],
                              find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"], match_type="ANY"))

    def test_find_duplicates_exclude_copied_cases(self):
        """cases that were copied using copy cases feature should not be considered as duplicates
        """
        cases = [
            self.factory.create_case(case_name=case_name, update={'dob': dob}) for (case_name, dob) in [
                ("Padme Amidala", "1901-05-01"),
                ("Padme Amidala", "1901-05-01"),
                ("Padme Amidala", "1901-05-01"),
                ("Anakin Skywalker", "1977-03-25"),
                ("Darth Vadar", "1977-03-25"),
            ]
        ]

        cases[2] = self.factory.update_case(
            case_id=cases[2].case_id,
            update={CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME: cases[0].case_id}
        )

        self._prime_es_index(cases)

        self.assertCountEqual(
            [cases[0].case_id, cases[1].case_id],
            find_duplicate_case_ids(self.domain, cases[0], ["name", "dob"], match_type="ALL")
        )

        self.assertCountEqual(
            [cases[0].case_id, cases[1].case_id, cases[2].case_id],
            find_duplicate_case_ids(
                self.domain, cases[0], ["name", "dob"], match_type="ALL", exclude_copied_cases=False
            )
        )

        self.assertCountEqual(
            [cases[3].case_id, cases[4].case_id],
            find_duplicate_case_ids(self.domain, cases[3], ["name", "dob"], match_type="ANY")
        )


@flag_enabled('CASE_DEDUPE_UPDATES')
class CaseDeduplicationActionTest(TestCase):
    def setUp(self):
        super().setUp()

        self.domain = 'case-dedupe-test'
        self.case_type = 'adult'
        self.factory = CaseFactory(self.domain)

        self.rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='test',
            case_type=self.case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        _, self.action = self.rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["name", "age"],
        )

        self.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='is_potential_duplicate',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='yes',
            )
        ])
        self.action.save()

        case_exists_patcher = patch('corehq.apps.data_interfaces.models._case_exists_in_es')
        self.case_exists_mock = case_exists_patcher.start()
        self.case_exists_mock.return_value = True
        self.addCleanup(case_exists_patcher.stop)

    def _create_cases(self, num_cases=5):
        faker = Faker()

        duplicates = [
            self._create_case(name='George Simon Esq.', age=12) for _ in range(num_cases)
        ]
        uniques = [
            self._create_case(name=faker.name(), age=faker.random_int(1, 100)) for _ in range(num_cases)
        ]

        return duplicates, uniques

    def _create_case(self, name='George Simon Esq.', age=12):
        return self.factory.create_case(case_name=name, case_type=self.case_type, update={'age': age})

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_updates_a_duplicate(self, find_duplicates_mock):
        """Ensure that all duplicates are updated by the rule
        """

        duplicates, uniques = self._create_cases()
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        for duplicate_case in duplicates:
            self.assertEqual(
                CommCareCase.objects.get_case(duplicate_case.case_id, self.domain)
                .get_case_property('is_potential_duplicate'),
                'yes',
            )

        for unique_case in uniques:
            self.assertIsNone(
                CommCareCase.objects.get_case(unique_case.case_id, self.domain)
                .get_case_property('is_potential_duplicate'),
            )

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
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
        form_transactions = CommCareCase.objects.get_case(
            duplicates[1].case_id, self.domain).get_form_transactions()
        self.assertEqual(2, len(form_transactions))

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_unique_not_updated(self, find_duplicates_mock):
        """Ensure that new unique cases are not updated
        """

        duplicates, uniques = self._create_cases(1)
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        for duplicate_case in duplicates:
            self.assertIsNone(
                CommCareCase.objects.get_case(duplicate_case.case_id, self.domain)
                .get_case_property('is_potential_duplicate'),
            )

        for unique_case in uniques:
            self.assertIsNone(
                CommCareCase.objects.get_case(unique_case.case_id, self.domain)
                .get_case_property('is_potential_duplicate'),
            )

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_stores_new_duplicate(self, find_duplicates_mock):
        """When it finds a duplicate, store it in the CaseDuplicate model
        """
        duplicates, _ = self._create_cases(num_cases=5)
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        # We only guarantee that the matching case and at least one other case will get inserted
        resulting_case_ids = CaseDuplicateNew.objects.filter(
            action=self.action).all().values_list('case_id', flat=True)
        self.assertIn(duplicates[0].case_id, resulting_case_ids)
        self.assertGreater(len(resulting_case_ids), 1)

    def test_calls_resave_cases_for_case_not_in_elasticsearch(self):
        duplicates, _ = self._create_cases(num_cases=1)
        self.case_exists_mock.return_value = False

        # Remove these lines when the old model is removed
        from corehq.apps.data_interfaces.models import CaseRuleActionResult
        with patch.object(CaseDeduplicationActionDefinition, '_handle_case_duplicate') as handle_case_duplicate:
            handle_case_duplicate.return_value = CaseRuleActionResult(num_updates=0)

            with patch('corehq.apps.data_interfaces.models.resave_case') as resave_case_mock:
                self.rule.run_actions_when_case_matches(duplicates[0])
                resave_case_mock.assert_called()

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_case_no_longer_duplicate(self, find_duplicates_mock):
        """When the case is no longer a duplicate, it should be removed from the CaseDuplicate model
        """
        case = self._create_case(age=12)
        CaseDuplicateNew.create(case, self.action)

        updated_case = self.factory.update_case(case.case_id, update={'age': 15})

        # The first case is no longer a duplicate
        find_duplicates_mock.return_value = [case.case_id]
        self.rule.run_actions_when_case_matches(updated_case)

        self.assertEqual(
            CaseDuplicateNew.objects.filter(action=self.action, case_id=case.case_id).count(), 0
        )

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_orphaned_case_is_removed(self, find_duplicates_mock):
        """A case that becomes unique due to an update can orphan the case that was previously
        considered a duplicate of it. Make sure that orphaned case is removed
        """
        duplicates, uniques = self._create_cases(num_cases=2)
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        updated_case = self.factory.update_case(duplicates[0].case_id, update={'age': 15})

        find_duplicates_mock.return_value = [duplicates[0].case_id]
        self.rule.run_actions_when_case_matches(updated_case)

        duplicate_ids = [case.case_id for case in duplicates]

        self.assertEqual(
            CaseDuplicateNew.objects.filter(action=self.action, case_id__in=duplicate_ids).count(), 0
        )

    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_case_already_marked_duplicate(self, find_duplicates_mock):
        """What happens when a case is already in the list
        """
        duplicates, uniques = self._create_cases(num_cases=2)
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        self.rule.run_actions_when_case_matches(duplicates[0])

        # Running a second time shouldn't change the results
        self.rule.run_actions_when_case_matches(duplicates[0])
        duplicate = CaseDuplicateNew.objects.get(action=self.action, case_id=duplicates[0].case_id)
        self.assertEqual(duplicate.case_id, duplicates[0].case_id)

    @patch.object(CaseDeduplicationActionDefinition, '_update_cases')
    @patch("corehq.apps.data_interfaces.models._find_duplicate_case_ids")
    def test_cases_not_fetched_no_updates(self, find_duplicates_mock, update_cases_mock):
        """Test that running a rule that has no updates doesn't fetch all the cases
        """
        duplicates, _ = self._create_cases()
        find_duplicates_mock.return_value = [duplicate.case_id for duplicate in duplicates]

        no_update_rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='test',
            case_type=self.case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        _, self.action = self.rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["name", "age"],
        )

        no_update_rule.run_actions_when_case_matches(duplicates[0])
        update_cases_mock.assert_not_called()

    def test_rule_activation(self):
        """Test that activating or deactivating a rule will trigger the right action
        """
        self.rule.active = False

        with patch("corehq.apps.data_interfaces.models.reset_and_backfill_deduplicate_rule") as backfill_patch:
            self.rule.activate()  # reactivate
            backfill_patch.assert_called_with(self.rule)

        with patch("corehq.apps.data_interfaces.models.reset_and_backfill_deduplicate_rule") as backfill_patch:
            self.rule.activate()  # This should do nothing, since the rule is already active
            backfill_patch.assert_not_called()

    def test_rule_deletion(self):
        """Test that deleting a rule will also delete case duplicates
        """
        duplicates, uniques = self._create_cases()
        CaseDuplicateNew.objects.bulk_create([
            CaseDuplicateNew(
                case_id=case.case_id, action=self.action, hash="abc"
            ) for case in duplicates])

        self.rule.soft_delete()
        self.assertEqual(CaseDuplicateNew.objects.filter(action=self.action).count(), 0)

    def test_case_deletion(self):
        """Test that deleting cases also deletes Duplicate Relationships
        """
        duplicates, _ = self._create_cases()
        duplicate_case_ids = [c.case_id for c in duplicates]
        duplicate_entries = [
            CaseDuplicateNew(case_id=case.case_id, action=self.action, hash='abc') for case in duplicates
        ]
        CaseDuplicateNew.objects.bulk_create(duplicate_entries)

        # Delete all cases except the last one, which is now no longer a duplicate.
        tag_cases_as_deleted_and_remove_indices(
            self.domain, duplicate_case_ids[0:-1], "deletion", datetime.utcnow()
        )

        # All CaseDuplicates should be deleted (including the last one)
        self.assertEqual(CaseDuplicateNew.objects.filter(case_id__in=duplicate_case_ids).count(), 0)

    @es_test(requires=[case_search_adapter])
    def test_integration_test(self):
        """Don't mock the find_duplicate_ids response to make sure it works
        """
        duplicates, uniques = self._create_cases()

        case_search_adapter.bulk_index(chain(duplicates, uniques), refresh=True)
        # Each run only ensures that it will insert itself and one other record if its a duplicate,
        # so run through all duplicates to ensure they all exist
        for i in range(len(duplicates)):
            self.rule.run_actions_when_case_matches(duplicates[i])

        duplicate = CaseDuplicateNew.objects.get(action=self.action, case_id=duplicates[0].case_id)
        results = set(CaseDuplicateNew.objects.filter(
            action=self.action, hash=duplicate.hash).values_list('case_id', flat=True))
        duplicate_case_ids = {c.case_id for c in duplicates}
        self.assertSetEqual(results, duplicate_case_ids)

    @es_test(requires=[case_search_adapter])
    def test_update_parent(self):
        duplicates, uniques = self._create_cases(num_cases=2)
        parent = uniques[0]
        child = duplicates[0]
        set_parent_case(self.domain, child, parent)
        case_search_adapter.bulk_index(chain(duplicates, uniques), refresh=True)

        new_parent_case_property_value = 'UpdatedName'
        self.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='parent/name',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value=new_parent_case_property_value,
            )
        ])
        self.action.save()
        self.rule = AutomaticUpdateRule.objects.get(id=self.rule.id)

        self.rule.run_actions_when_case_matches(child)

        updated_parent_case = CommCareCase.objects.get_case(parent.case_id, self.domain)
        self.assertEqual(updated_parent_case.get_case_property('name'), new_parent_case_property_value)


@override_settings(RUN_UNKNOWN_USER_PILLOW=False)
@override_settings(RUN_FORM_META_PILLOW=False)
@flag_enabled('CASE_DEDUPE_UPDATES')
class DeduplicationPillowTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'naboo'
        cls.case_type = 'people'
        cls.factory = CaseFactory(cls.domain)
        cls.pillow = get_case_pillow(skip_ucr=True)

    def setUp(self):
        self.kafka_offset = get_topic_offset(topics.CASE_SQL)

        find_duplicates_patcher = patch('corehq.apps.data_interfaces.models._find_duplicate_case_ids')
        self.find_duplicates_mock = find_duplicates_patcher.start()
        self.addCleanup(find_duplicates_patcher.stop)

        case_exists_patcher = patch('corehq.apps.data_interfaces.models._case_exists_in_es')
        self.case_exists_mock = case_exists_patcher.start()
        self.case_exists_mock.return_value = True
        self.addCleanup(case_exists_patcher.stop)

    def test_pillow_processes_changes(self):
        rule = self._create_rule('test', ["age"])
        self._configure_properties_to_update(rule, {"name": "Herman Miller", "age": "5"})

        case1 = self.factory.create_case(case_type=self.case_type, update={"age": 2})
        case2 = self.factory.create_case(case_type=self.case_type, update={"age": 2})

        self.find_duplicates_mock.return_value = [case1.case_id, case2.case_id]

        new_kafka_sec = get_topic_offset(topics.CASE_SQL)
        self.pillow.process_changes(since=self.kafka_offset, forever=False)

        self.assertEqual(CaseDuplicateNew.objects.count(), 2)
        self.assertEqual(CommCareCase.objects.get_case(case1.case_id, self.domain).get_case_property('age'), '5')
        self.assertEqual(CommCareCase.objects.get_case(case1.case_id, self.domain).name, 'Herman Miller')

        self.pillow.process_changes(since=new_kafka_sec, forever=False)

    def test_pillow_ignores_deduplication_changes(self):
        rule = self._create_rule('test', ["age"])
        self._configure_properties_to_update(rule, {"name": "Herman Miller", "age": "5"})

        case = self.factory.create_case(case_type=self.case_type, update={"age": 2})
        self.find_duplicates_mock.return_value = [case.case_id, 'test_id']

        new_kafka_sec = get_topic_offset(topics.CASE_SQL)
        self.pillow.process_changes(since=self.kafka_offset, forever=False)

        with patch('corehq.apps.data_interfaces.pillow.run_rules_for_case') as p:
            self.pillow.process_changes(since=new_kafka_sec, forever=False)
            p.assert_not_called()

    def test_pillow_processes_normalized_system_properties(self):
        rule = self._create_rule('system_prop_test', ['name'])
        action = CaseDeduplicationActionDefinition.from_rule(rule)

        case = self.factory.create_case(case_name="foo", case_type=self.case_type)

        self.find_duplicates_mock.return_value = [case.case_id, 'duplicate_case_id']

        self.pillow.process_changes(since=self.kafka_offset, forever=False)

        hash = CaseDuplicateNew.case_and_action_to_hash(case, action)
        results = CaseDuplicateNew.objects.filter(
            action=action, hash=hash).values_list('case_id', flat=True)

        self.assertSetEqual(set(results), {case.case_id, 'duplicate_case_id'})

    def test_pillow_processes_resaves(self):
        rule = self._create_rule('test', ['age'])
        action = CaseDeduplicationActionDefinition.from_rule(rule)

        case = self.factory.create_case(case_type=self.case_type, update={"age": 2})
        new_kafka_sec = get_topic_offset(topics.CASE_SQL)
        resave_case(self.domain, case, send_post_save_signal=False)

        self.find_duplicates_mock.return_value = [case.case_id, 'duplicate_case_id']

        self.pillow.process_changes(since=new_kafka_sec, forever=False)

        hash = CaseDuplicateNew.case_and_action_to_hash(case, action)
        results = CaseDuplicateNew.objects.filter(
            action=action, hash=hash).values_list('case_id', flat=True)

        self.assertSetEqual(set(results), {case.case_id, 'duplicate_case_id'})

    def _create_rule(self, name='test', match_on=None):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name=name,
            case_type=self.case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE
        )

        match_on = match_on or []

        rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=match_on
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

        return rule

    def _configure_properties_to_update(self, rule, prop_map):
        action = rule.memoized_actions[0].definition
        action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name=name,
                value=value,
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
            ) for (name, value) in prop_map.items()
        ])
        action.save()


@flag_enabled('CASE_DEDUPE_UPDATES')
@es_test(requires=[case_search_adapter, user_adapter])
class TestDeduplicationRuleRuns(TestCase):
    def setUp(self):
        super().setUp()

        self.case_type = 'duck'
        self.domain = 'naboo'
        self.domain_obj = create_domain(self.domain)
        self.factory = CaseFactory(self.domain)

    def tearDown(self):
        self.domain_obj.delete()
        super().tearDown()

    def create_rule(self, rule_name, case_type):
        return AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name=rule_name,
            case_type=case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )

    def _create_mobile_worker(self, username):
        return CommCareUser.create(
            domain=self.domain,
            username=username,
            password="*****",
            created_by=None,
            created_via=None,
            metadata=None,
        )

    def _prime_es_index(self, cases):
        case_search_adapter.bulk_index(cases, refresh=True)

    def _send_user_to_es(self, user):
        with patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', return_value=[]):
            user_adapter.index(user, refresh=True)
        return user

    def get_case_property_value(self, case, property_value):
        return next((prop['value'] for prop in case['case_properties'] if prop['key'] == property_value))

    def test_simple_rule(self):
        cases = [
            self.factory.create_case(case_name="Anakin Skywalker", update={'age': '14'}),
            self.factory.create_case(case_name="Darth Vadar", update={'age': '14'}),
        ]

        for case in cases:
            case.type = self.case_type

        self._prime_es_index(cases)

        rule = self.create_rule(rule_name='Testy Rule', case_type=self.case_type)

        _, self.action = rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["age"],
        )

        self.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='age',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='41',
            ),
        ])
        self.action.save()

        cases_ids = []
        for case in cases:
            cases_ids.append(case.case_id)
            run_rules_for_case(case, [rule], datetime.utcnow())

        refreshed_cases = CommCareCase.objects.get_cases(cases_ids, self.domain)
        self.assertEqual(len(refreshed_cases), 2)
        self.assertTrue(refreshed_cases[0].get_case_property('age') == '41')
        self.assertTrue(refreshed_cases[1].get_case_property('age') == '41')

    def test_rule_with_closed_cases(self):
        cases = [
            self.factory.create_case(case_name="Anakin Skywalker", update={'age': '14', 'is_evil': '1'}),
            self.factory.create_case(case_name="Darth Vadar", update={'age': '14', 'is_evil': '1'}),
        ]

        for case in cases:
            case.type = self.case_type

        cases[0].closed = True
        cases[0].save()

        self._prime_es_index(cases)

        rule = self.create_rule(rule_name='Testy Rule', case_type=self.case_type)

        _, self.action = rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["is_evil"],
            include_closed=True,
        )

        self.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='age',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='41',
            ),
        ])
        self.action.save()

        cases_ids = []
        for case in cases:
            cases_ids.append(case.case_id)
            run_rules_for_case(case, [rule], datetime.utcnow())

        refreshed_cases = CommCareCase.objects.get_cases(cases_ids, self.domain)

        self.assertEqual(len(refreshed_cases), 2)
        self.assertTrue(refreshed_cases[0].get_case_property('age') == '41')
        self.assertTrue(refreshed_cases[1].get_case_property('age') == '41')

    def test_rule_with_location_as_owner(self):
        cases = [
            self.factory.create_case(case_name="Anakin Skywalker", update={'age': '14'}),
            self.factory.create_case(case_name="Darth Vadar", update={'age': '14'}),
            self.factory.create_case(case_name="Wannabe Anakin Skywalker", update={'age': '14'}),
            self.factory.create_case(case_name="Wannabe Darth Vadar", update={'age': '14'}),
        ]

        for case in cases:
            case.type = self.case_type

        from corehq.apps.locations.models import LocationType, make_location
        loc_type = LocationType.objects.create(
            name='place',
            domain=self.domain,
        )
        location = make_location(
            domain=self.domain,
            location_type=loc_type.name,
            name='Mustafar'
        )
        location.save()
        location_id = location.location_id

        # Only assign location id to first 2 cases, since we want only those two cases to be considered
        cases[0].owner_id = location_id
        cases[1].owner_id = location_id

        real_cases = [
            cases[0].case_id,
            cases[1].case_id,
        ]
        fake_cases = [
            cases[2].case_id,
            cases[3].case_id,
        ]

        self._prime_es_index(cases)
        rule = self.create_rule(rule_name='Testy Rule', case_type=self.case_type)

        # Create rule criteria
        definition = LocationFilterDefinition.objects.create(
            location_id=location.location_id,
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        # Create rule actions
        _, self.action = rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["age"],
        )

        self.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='age',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='41',
            ),
        ])
        self.action.save()

        cases_ids = []
        for case in cases:
            cases_ids.append(case.case_id)
            run_rules_for_case(case, [rule], datetime.utcnow())

        refreshed_cases = CommCareCase.objects.get_cases(cases_ids, self.domain)

        refreshed_real_cases = [case for case in refreshed_cases if case.case_id in real_cases]
        refreshed_fake_cases = [case for case in refreshed_cases if case.case_id in fake_cases]

        self.assertEqual(refreshed_real_cases[0].get_case_property('age'), '41')
        self.assertEqual(refreshed_real_cases[1].get_case_property('age'), '41')

        self.assertEqual(refreshed_fake_cases[0].get_case_property('age'), '14')
        self.assertEqual(refreshed_fake_cases[1].get_case_property('age'), '14')

    def test_rule_with_user_as_owner(self):
        cases = [
            self.factory.create_case(case_name="Anakin Skywalker", update={'age': '14'}),
            self.factory.create_case(case_name="Darth Vadar", update={'age': '14'}),
            self.factory.create_case(case_name="Wannabe Anakin Skywalker", update={'age': '14'}),
            self.factory.create_case(case_name="Wannabe Darth Vadar", update={'age': '14'}),
        ]

        for case in cases:
            case.type = self.case_type

        from corehq.apps.locations.models import LocationType, make_location
        loc_type = LocationType.objects.create(
            name='place',
            domain=self.domain,
        )
        location = make_location(
            domain=self.domain,
            location_type=loc_type.name,
            name='Mustafar'
        )
        location.save()

        user = self._create_mobile_worker('Location User')
        user.set_location(location)

        self._send_user_to_es(user)

        cases[0].owner_id = user.user_id
        cases[1].owner_id = user.user_id

        real_cases = [
            cases[0].case_id,
            cases[1].case_id,
        ]
        fake_cases = [
            cases[2].case_id,
            cases[3].case_id,
        ]

        self._prime_es_index(cases)
        rule = self.create_rule(rule_name='Testy Rule', case_type=self.case_type)

        # Create rule criteria
        definition = LocationFilterDefinition.objects.create(
            location_id=location.location_id,
        )
        criteria = CaseRuleCriteria(rule=rule)
        criteria.definition = definition
        criteria.save()

        # Create rule actions
        _, self.action = rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["age"],
        )

        self.action.set_properties_to_update([
            CaseDeduplicationActionDefinition.PropertyDefinition(
                name='age',
                value_type=CaseDeduplicationActionDefinition.VALUE_TYPE_EXACT,
                value='41',
            ),
        ])
        self.action.save()

        cases_ids = []
        for case in cases:
            cases_ids.append(case.case_id)
            run_rules_for_case(case, [rule], datetime.utcnow())

        refreshed_cases = CommCareCase.objects.get_cases(cases_ids, self.domain)

        refreshed_real_cases = [case for case in refreshed_cases if case.case_id in real_cases]
        refreshed_fake_cases = [case for case in refreshed_cases if case.case_id in fake_cases]

        self.assertEqual(refreshed_real_cases[0].get_case_property('age'), '41')
        self.assertEqual(refreshed_real_cases[1].get_case_property('age'), '41')

        self.assertEqual(refreshed_fake_cases[0].get_case_property('age'), '14')
        self.assertEqual(refreshed_fake_cases[1].get_case_property('age'), '14')


@flag_enabled('CASE_DEDUPE_UPDATES')
@es_test(requires=[case_search_adapter], setup_class=True)
class DeduplicationBackfillTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'naboo'
        cls.domain_obj = create_domain(cls.domain)
        cls.case_type = 'people'
        cls.factory = CaseFactory(cls.domain)

        cls.case1 = cls.factory.create_case(
            case_name="foo", case_type=cls.case_type, update={"age": 2}, close=True
        )
        cls.case2 = cls.factory.create_case(case_name="foo", case_type=cls.case_type, update={"age": 2})
        cls.case3 = cls.factory.create_case(case_name="foo", case_type=cls.case_type, update={"age": 2})
        cls.case4 = cls.factory.create_case(
            case_name="foo", case_type=cls.case_type,
            update={"age": 2, CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME: cls.case1.case_id}
        )

        case_search_adapter.bulk_index([cls.case1, cls.case2, cls.case3, cls.case4], refresh=True)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        return super().tearDownClass()

    def _set_up_rule(self, include_closed):
        self.rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='test',
            case_type=self.case_type,
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        _, self.action = self.rule.add_action(
            CaseDeduplicationActionDefinition,
            match_type=CaseDeduplicationMatchTypeChoices.ALL,
            case_properties=["case_name", "age"],
            include_closed=include_closed
        )

        self.action.save()
        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

    def test_include_closed_finds_open_and_closed_cases(self):
        self._set_up_rule(include_closed=True)

        backfill_deduplicate_rule(self.domain, self.rule)

        duplicate_case_ids = CaseDuplicateNew.objects.filter(action=self.action).values_list('case_id', flat=True)
        self.assertEqual(len(duplicate_case_ids), 3)
        self.assertNotIn(self.case4.case_id, duplicate_case_ids)

    def test_finds_open_cases_only(self):
        self._set_up_rule(include_closed=False)

        backfill_deduplicate_rule(self.domain, self.rule)

        duplicate_case_ids = CaseDuplicateNew.objects.filter(action=self.action).values_list('case_id', flat=True)
        self.assertEqual(len(duplicate_case_ids), 2)
        self.assertNotIn(self.case4.case_id, duplicate_case_ids)
