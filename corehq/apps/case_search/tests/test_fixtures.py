import uuid
from unittest.mock import patch

from django.test import TestCase

from lxml import etree

from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.tests.utils import call_fixture_generator

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import case_search_es_setup, es_test
from corehq.apps.users.models import WebUser
from corehq.tests.util.xml import assert_xml_equal, assert_xml_partial_equal
from corehq.util.test_utils import flag_enabled

from ..fixtures import _get_template_renderer, case_search_fixture_generator


@flag_enabled('MODULE_BADGES')
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

    def generate_fixture(self):
        res = call_fixture_generator(case_search_fixture_generator, self.restore_user, self.domain_obj)
        return etree.tostring(next(res), encoding='utf-8')

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

    @patch('corehq.apps.case_search.fixtures._get_indicators')
    @patch('corehq.apps.case_search.fixtures._run_query')
    def test_fixture_generator(self, run_query, get_indicators):
        run_query.return_value = "42"
        get_indicators.return_value = [
            ('pre_pandemic_births', "dob < '2020-01-01'"),
            ('owned_by_user', "@owner_id = '{user.uuid}'"),
        ]

        expected = """
        <fixture id="case-search-fixture">
           <values>
               <value name="pre_pandemic_births">42</value>
               <value name="owned_by_user">42</value>
           </values>
        </fixture>"""
        assert_xml_equal(expected, self.generate_fixture())

    @patch('corehq.apps.case_search.fixtures._get_indicators')
    def test_full_query(self, get_indicators):
        indicators = [
            # (name, csql_template, expected_count)
            ('owned_by_user', "@owner_id = '{user.uuid}'", 3),
            ('total_clients', "@case_type = 'client'", 3),
            ('own_clients', "@case_type = 'client' and @owner_id = '{user.uuid}'", 2),
            ('bad_query', "this is not a valid query", "ERROR"),
        ]
        get_indicators.return_value = [(name, csql_template) for name, csql_template, _ in indicators]

        res = self.generate_fixture()
        for name, _, expected in indicators:
            expected_xml = f'<partial><value name="{name}">{expected}</value></partial>'
            assert_xml_partial_equal(expected_xml, res, f'./values/value[@name="{name}"]')
