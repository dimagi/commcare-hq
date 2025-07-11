import uuid
from unittest.mock import patch

from django.test import TestCase

from lxml import etree
from lxml.builder import E

from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.tests.utils import call_fixture_generator

from corehq.apps.case_search.models import CSQLFixtureExpression
from corehq.apps.case_search.fixtures import _get_indicators_for_user
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import case_search_es_setup, es_test
from corehq.apps.users.models import WebUser
from corehq.tests.util.xml import assert_xml_equal, assert_xml_partial_equal
from corehq.util.test_utils import flag_enabled

from ..fixtures import _get_template_renderer, case_search_fixture_generator


@flag_enabled('CSQL_FIXTURE')
@es_test(requires=[case_search_adapter], setup_class=True)
class TestCaseSearchFixtures(TestCase):
    domain_name = 'test-case-search-fixtures'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.user = WebUser.create(cls.domain_name, 'test@example.com', 'secret', None, None)
        cls.restore_user = cls.user.to_ota_restore_user(cls.domain_name)
        case_search_es_setup(cls.domain_name, cls._get_case_blocks(cls.user.user_id))
        cls.addClassCleanup(cls.domain_obj.delete)

    @staticmethod
    def _get_case_blocks(owner_id):
        def case_block(case_type, name, owner_id):
            return CaseBlock(
                case_id=str(uuid.uuid4()),
                case_type=case_type,
                case_name=name,
                owner_id=owner_id,
                create=True,
            )

        return [
            case_block('client', 'Kleo', owner_id),
            case_block('client', 'Sven', owner_id),
            case_block('client', 'Thilo', '---'),
            case_block('place', 'Berlin', owner_id),
            case_block('place', 'Sirius B', '---'),
        ]

    def render(self, template_string):
        return _get_template_renderer(self.restore_user).render(template_string)

    def generate_fixtures(self):
        res = E.TestRestore(
            *call_fixture_generator(case_search_fixture_generator, self.restore_user, self.domain_obj)
        )
        return etree.tostring(res, encoding='utf-8')

    def test_no_interpolation(self):
        res = self.render("dob < '2020-01-01'")
        self.assertEqual(res, "dob < '2020-01-01'")

    def test_user_id(self):
        res = self.render("@owner_id = '{user.uuid}'")
        self.assertEqual(res, f"@owner_id = '{self.user.user_id}'")

    @patch('custom.bha.commcare_extensions.get_user_clinic_ids')
    def test_bha_custom_csql_fixture_context(self, get_user_clinic_ids):
        self.restore_user.domain = 'co-carecoordination'

        def reset_domain():
            self.restore_user.domain = self.domain_name
        self.addCleanup(reset_domain)

        get_user_clinic_ids.return_value = "abc123 def456"
        res = self.render("selected(@owner_id, '{bha.user_clinic_ids}')")
        self.assertEqual(res, "selected(@owner_id, 'abc123 def456')")

    @patch('corehq.apps.case_search.fixtures._get_indicators_for_user')
    @patch('corehq.apps.case_search.fixtures._run_query')
    def test_fixture_generator(self, run_query, get_indicators_for_user):
        run_query.return_value = "42"
        get_indicators_for_user.return_value = [
            ('pre_pandemic_births', "dob < '2020-01-01'"),
            ('owned_by_user', "@owner_id = '{user.uuid}'"),
        ]

        expected = """
        <TestRestore>
            <fixture id="case-search-fixture:pre_pandemic_births">
                <value>42</value>
            </fixture>
            <fixture id="case-search-fixture:owned_by_user">
                <value>42</value>
            </fixture>
        </TestRestore>"""
        assert_xml_equal(expected, self.generate_fixtures())

    @patch('corehq.apps.case_search.fixtures._get_indicators_for_user')
    def test_full_query(self, get_indicators_for_user):
        indicators = [
            # (name, csql_template, expected_count)
            ('owned_by_user', "@owner_id = '{user.uuid}'", 3),
            ('total_clients', "@case_type = 'client'", 3),
            ('own_clients', "@case_type = 'client' and @owner_id = '{user.uuid}'", 2),
            ('bad_query', "this is not a valid query", "ERROR"),
        ]
        get_indicators_for_user.return_value = [(name, csql_template) for name, csql_template, _ in indicators]

        res = self.generate_fixtures()
        for name, _, expected in indicators:
            expected_xml = f'<partial><value>{expected}</value></partial>'
            assert_xml_partial_equal(
                expected_xml, res, f'./fixture[@id="case-search-fixture:{name}"]/value')


class TestGetIndicatorsForUser(TestCase):
    def setUp(self):
        self.domain = 'test-domain'
        create_domain(self.domain)

        self.user1 = self._create_user('user1@example.com', {'is_active': True, 'is_superuser': False})
        self.user2 = self._create_user('user2@example.com', {'is_active': 'nonboolean', 'is_superuser': False})
        self.user3 = self._create_user('user3@example.com', {'is_active': '', 'is_superuser': False})
        self.user4 = self._create_user('user4@example.com', {'non_filtered_field': True})

        self.matching_expression = CSQLFixtureExpression.objects.create(
            domain=self.domain,
            name='matching_expression',
            csql='matching_csql',
            user_data_criteria=[
                {'operator': 'IS', 'property_name': 'is_active'},
                {'operator': 'IS_NOT', 'property_name': 'is_superuser'},
            ]
        )
        self.addCleanup(self.matching_expression.delete)

        self.non_matching_expression = CSQLFixtureExpression.objects.create(
            domain=self.domain,
            name='non_matching_expression',
            csql='non_matching_csql',
            user_data_criteria=[
                {'operator': 'IS', 'property_name': 'is_active'},
                {'operator': 'IS', 'property_name': 'is_superuser'},
            ]
        )
        self.addCleanup(self.non_matching_expression.delete)

        self.non_existing_criteria_field_expression = CSQLFixtureExpression.objects.create(
            domain=self.domain,
            name='non_existing_criteria_field_expression',
            csql='non_existing_criteria_field_csql',
            user_data_criteria=[
                {'operator': 'IS', 'property_name': 'non_existing_criteria_field'},
            ]
        )
        self.addCleanup(self.non_existing_criteria_field_expression.delete)

    def _create_user(self, email, user_data):
        user = WebUser.create(self.domain, email, '****', None, None, user_data=user_data)
        self.addCleanup(user.delete, self.domain, None)
        return user

    def test_user_with_valid_data(self):
        indicators = _get_indicators_for_user(self.domain, self.user1)
        expected_indicators = {self.matching_expression, self.non_existing_criteria_field_expression}
        for indicator in expected_indicators:
            self.assertIn((indicator.name, indicator.csql), indicators)
        self.assertEqual(len(indicators), 2)

    def test_user_with_non_boolean_value(self):
        indicators = _get_indicators_for_user(self.domain, self.user2)
        expected_indicators = {self.matching_expression, self.non_existing_criteria_field_expression}
        for indicator in expected_indicators:
            self.assertIn((indicator.name, indicator.csql), indicators)
        self.assertEqual(len(indicators), 2)

    def test_user_with_blank_value(self):
        indicators = _get_indicators_for_user(self.domain, self.user3)
        expected_indicators = {self.matching_expression, self.non_existing_criteria_field_expression}
        for indicator in expected_indicators:
            self.assertIn((indicator.name, indicator.csql), indicators)
        self.assertEqual(len(indicators), 2)

    def test_user_with_non_existent_field(self):
        indicators = _get_indicators_for_user(self.domain, self.user4)
        expected_indicators = {self.matching_expression, self.non_existing_criteria_field_expression,
                               self.non_matching_expression}
        for indicator in expected_indicators:
            self.assertIn((indicator.name, indicator.csql), indicators)
        self.assertEqual(len(indicators), 3)
