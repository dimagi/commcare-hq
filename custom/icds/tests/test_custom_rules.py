from __future__ import absolute_import
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CustomMatchDefinition, CustomActionDefinition
from corehq.apps.data_interfaces.tests.test_auto_case_updates import (
    BaseCaseRuleTest,
    _create_empty_rule,
    _with_case,
)
from corehq.apps.data_interfaces.tests.util import create_case, create_empty_rule
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from custom.icds.const import AWC_LOCATION_TYPE_CODE, SUPERVISOR_LOCATION_TYPE_CODE
from custom.icds.rules.util import todays_date
from datetime import datetime, date


@use_sql_backend
class AutoEscalationTest(BaseCaseRuleTest):
    domain = 'icds-auto-escalation-test'

    @property
    def todays_date_as_str(self):
        return todays_date(datetime.utcnow()).strftime('%Y-%m-%d')

    def _test_auto_escalation(self, from_level, to_level):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rule.add_action(CustomActionDefinition, name='ICDS_ESCALATE_TECH_ISSUE')

        with create_case(
            self.domain,
            'tech_issue',
            case_name='New Issue',
            update={
                'ticket_level': from_level,
                'touch_case_date': '2017-06-01',
                'block_location_id': 'block_id',
                'district_location_id': 'district_id',
                'state_location_id': 'state_id',
            },
        ) as tech_issue:
            properties = tech_issue.to_json()
            self.assertEqual(properties.get('ticket_level'), from_level)
            self.assertEqual(properties.get('touch_case_date'), '2017-06-01')
            self.assertIsNone(properties.get('change_in_level'))

            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 1)
            self.assertEqual(result.num_creates, 1)

            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)
            properties = tech_issue.to_json()
            self.assertEqual(properties.get('ticket_level'), to_level)
            self.assertEqual(properties.get('touch_case_date'), self.todays_date_as_str)
            self.assertEqual(properties.get('change_in_level'), '1')

            subcases = tech_issue.get_subcases(index_identifier='parent')
            self.assertEqual(len(subcases), 1)
            [tech_issue_delegate] = subcases

            self.assertEqual(tech_issue_delegate.type, 'tech_issue_delegate')
            self.assertEqual(tech_issue_delegate.name, tech_issue.name)
            self.assertEqual(tech_issue_delegate.owner_id,
                tech_issue.get_case_property('%s_location_id' % to_level))
            self.assertEqual(tech_issue_delegate.get_case_property('change_in_level'), '1')

    def test_auto_escalation_to_block(self):
        self._test_auto_escalation('supervisor', 'block')

    def test_auto_escalation_to_district(self):
        self._test_auto_escalation('block', 'district')

    def test_auto_escalation_to_state(self):
        self._test_auto_escalation('district', 'state')

    def test_no_further_escalation(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rule.add_action(CustomActionDefinition, name='ICDS_ESCALATE_TECH_ISSUE')

        with create_case(
            self.domain,
            'tech_issue',
            case_name='New Issue',
            update={'ticket_level': 'state'},
        ) as tech_issue:
            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 0)
            self.assertEqual(result.num_creates, 0)

    def test_when_delegate_exists(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rule.add_action(CustomActionDefinition, name='ICDS_ESCALATE_TECH_ISSUE')

        with create_case(
            self.domain,
            'tech_issue',
            case_name='New Issue',
            update={
                'ticket_level': 'block',
                'touch_case_date': '2017-06-01',
                'block_location_id': 'block_id',
                'district_location_id': 'district_id',
                'state_location_id': 'state_id',
            },
        ) as tech_issue:
            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 1)
            self.assertEqual(result.num_creates, 1)
            self.assertEqual(result.num_related_updates, 0)

            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)
            subcases = tech_issue.get_subcases(index_identifier='parent')
            self.assertEqual(len(subcases), 1)
            [tech_issue_delegate] = subcases
            self.assertEqual(tech_issue_delegate.get_case_property('change_in_level'), '1')

            update_case(self.domain, tech_issue.case_id, case_properties={'ticket_level': 'block'})
            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)

            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 1)
            self.assertEqual(result.num_creates, 0)
            self.assertEqual(result.num_related_updates, 1)

            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)
            subcases = tech_issue.get_subcases(index_identifier='parent')
            self.assertEqual(len(subcases), 1)
            [tech_issue_delegate] = subcases
            self.assertEqual(tech_issue_delegate.get_case_property('change_in_level'), '2')


@use_sql_backend
class CustomCriteriaTestCase(BaseCaseRuleTest):
    domain = 'icds-custom-criteria-test'

    @classmethod
    def setUpClass(cls):
        super(CustomCriteriaTestCase, cls).setUpClass()

        cls.domain_obj = create_domain(cls.domain)

        location_type_structure = [
            LocationTypeStructure(SUPERVISOR_LOCATION_TYPE_CODE, [
                LocationTypeStructure(AWC_LOCATION_TYPE_CODE, [])
            ])
        ]

        location_structure = [
            LocationStructure('LS1', SUPERVISOR_LOCATION_TYPE_CODE, [
                LocationStructure('AWC1', AWC_LOCATION_TYPE_CODE, []),
            ])
        ]

        cls.loc_types = setup_location_types_with_structure(cls.domain, location_type_structure)
        cls.locs = setup_locations_with_structure(cls.domain, location_structure)

        cls.ls = cls._make_user('ls', cls.locs['LS1'])
        cls.aww = cls._make_user('aww', cls.locs['AWC1'])

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password')
        user.set_location(location)
        return user

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(CustomCriteriaTestCase, cls).tearDownClass()

    def test_todays_date(self):
        # Test the boundary between today and tomorrow IST, expressed in UTC timestamps
        self.assertEqual(todays_date(datetime(2018, 2, 22, 18, 29)), date(2018, 2, 22))
        self.assertEqual(todays_date(datetime(2018, 2, 22, 18, 30)), date(2018, 2, 23))

    def _set_dob(self, case, dob):
        update_case(self.domain, case.case_id, case_properties={'dob': dob})
        return CaseAccessors(self.domain).get_case(case.case_id)

    def test_person_case_is_under_6_years_old(self):
        rule = _create_empty_rule(self.domain, case_type='person')
        rule.add_criteria(CustomMatchDefinition, name='ICDS_PERSON_CASE_IS_UNDER_6_YEARS_OLD')

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            # No value for dob yet
            self.assertFalse(rule.criteria_match(case, datetime(2018, 2, 22, 12, 0)))

            # Bad value for dob
            case = self._set_dob(case, 'x')
            self.assertFalse(rule.criteria_match(case, datetime(2018, 2, 22, 12, 0)))

            # Set dob
            case = self._set_dob(case, '2018-02-22')

            # Test over 6 years old
            self.assertFalse(rule.criteria_match(case, datetime(2024, 2, 22, 12, 0)))
            self.assertFalse(rule.criteria_match(case, datetime(2024, 5, 22, 12, 0)))

            # Test under 6 years old
            self.assertTrue(rule.criteria_match(case, datetime(2024, 2, 21, 12, 0)))
            self.assertTrue(rule.criteria_match(case, datetime(2018, 5, 22, 12, 0)))

        # Test wrong case type
        rule = _create_empty_rule(self.domain, case_type='x')
        rule.add_criteria(CustomMatchDefinition, name='ICDS_PERSON_CASE_IS_UNDER_6_YEARS_OLD')

        with _with_case(self.domain, 'x', datetime.utcnow()) as case:
            case = self._set_dob(case, '2018-02-22')
            self.assertFalse(rule.criteria_match(case, datetime(2018, 5, 22, 12, 0)))

    def test_is_usercase_of_aww(self):
        rule = _create_empty_rule(self.domain, case_type=USERCASE_TYPE)
        rule.add_criteria(CustomMatchDefinition, name='ICDS_IS_USERCASE_OF_AWW')

        with _with_case(self.domain, USERCASE_TYPE, datetime.utcnow(), owner_id=self.aww.get_id) as aww_uc,\
                _with_case(self.domain, USERCASE_TYPE, datetime.utcnow(), owner_id=self.ls.get_id) as ls_uc:

            self.assertTrue(rule.criteria_match(aww_uc, datetime.utcnow()))
            self.assertFalse(rule.criteria_match(ls_uc, datetime.utcnow()))

    def test_is_usercase_of_ls(self):
        rule = _create_empty_rule(self.domain, case_type=USERCASE_TYPE)
        rule.add_criteria(CustomMatchDefinition, name='ICDS_IS_USERCASE_OF_LS')

        with _with_case(self.domain, USERCASE_TYPE, datetime.utcnow(), owner_id=self.aww.get_id) as aww_uc,\
                _with_case(self.domain, USERCASE_TYPE, datetime.utcnow(), owner_id=self.ls.get_id) as ls_uc:

            self.assertFalse(rule.criteria_match(aww_uc, datetime.utcnow()))
            self.assertTrue(rule.criteria_match(ls_uc, datetime.utcnow()))
