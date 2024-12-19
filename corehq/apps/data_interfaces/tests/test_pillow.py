from django.test import TestCase, override_settings
from unittest.mock import patch
from corehq.util.test_utils import flag_enabled
from casexml.apps.case.mock import CaseFactory
from corehq.pillows.case import get_case_pillow
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.topics import get_topic_offset

from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseDuplicateNew,
    CaseDeduplicationMatchTypeChoices,
    CaseDeduplicationActionDefinition
)
from corehq.form_processor.models import CommCareCase
from corehq.apps.hqcase.utils import resave_case
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE

from corehq.form_processor.tests.utils import create_case
from corehq.form_processor.change_publishers import publish_case_saved


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
        rule = self._create_rule('test', ['age'])
        self._configure_properties_to_update(rule, {'name': 'Herman Miller', 'age': '5'})

        case1 = self.factory.create_case(case_type=self.case_type, update={'age': 2})
        case2 = self.factory.create_case(case_type=self.case_type, update={'age': 2})

        self.find_duplicates_mock.return_value = [case1.case_id, case2.case_id]

        new_kafka_sec = get_topic_offset(topics.CASE_SQL)
        self.pillow.process_changes(since=self.kafka_offset, forever=False)

        self.assertEqual(CaseDuplicateNew.objects.count(), 2)
        self.assertEqual(CommCareCase.objects.get_case(case1.case_id, self.domain).get_case_property('age'), '5')
        self.assertEqual(CommCareCase.objects.get_case(case1.case_id, self.domain).name, 'Herman Miller')

        self.pillow.process_changes(since=new_kafka_sec, forever=False)

    def test_pillow_ignores_deduplication_changes(self):
        rule = self._create_rule('test', ['age'])
        self._configure_properties_to_update(rule, {'name': 'Herman Miller', 'age': '5'})

        case = self.factory.create_case(case_type=self.case_type, update={'age': 2})
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

        case = self.factory.create_case(case_type=self.case_type, update={'age': 2})
        new_kafka_sec = get_topic_offset(topics.CASE_SQL)
        resave_case(self.domain, case, send_post_save_signal=False)

        self.find_duplicates_mock.return_value = [case.case_id, 'duplicate_case_id']

        self.pillow.process_changes(since=new_kafka_sec, forever=False)

        hash = CaseDuplicateNew.case_and_action_to_hash(case, action)
        results = CaseDuplicateNew.objects.filter(
            action=action, hash=hash).values_list('case_id', flat=True)

        self.assertSetEqual(set(results), {case.case_id, 'duplicate_case_id'})

    @patch('corehq.apps.data_interfaces.pillow.run_rules_for_case')
    def test_pillow_skips_commtrack_cases(self, mock_run_rules):
        self._create_rule()
        case = self.factory.create_case(case_type=USER_LOCATION_OWNER_MAP_TYPE)
        case.opened_by = None
        case.save()

        self.pillow.process_changes(since=self.kafka_offset, forever=False)

        mock_run_rules.assert_not_called()

    def test_pillow_processes_restored_forms(self):
        # This test was created to ensure that 'Undo-ing' a delete, or archiving a deletion request,
        # was not causing the correct deduplication logic to occur.
        # Because, from the code's perspective, these situations both just appear
        # as a case published without an associated form, that is what is being tested here
        rule = self._create_rule('test', ['name'])
        action = CaseDeduplicationActionDefinition.from_rule(rule)
        case1 = create_case(domain=self.domain, name='test', case_type=self.case_type, save=True)
        case2 = create_case(domain=self.domain, name='test', case_type=self.case_type, save=True)
        publish_case_saved(case1)

        self.find_duplicates_mock.return_value = [case1.case_id, case2.case_id]

        self.pillow.process_changes(since=self.kafka_offset, forever=False)

        hash = CaseDuplicateNew.case_and_action_to_hash(case1, action)
        resulting_ids = CaseDuplicateNew.objects.filter(action=action, hash=hash).values_list('case_id', flat=True)
        self.assertIn(case1.case_id, resulting_ids)

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
