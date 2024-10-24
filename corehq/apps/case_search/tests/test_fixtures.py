from unittest.mock import patch

from django.test import TestCase

from lxml import etree

from casexml.apps.phone.tests.utils import call_fixture_generator

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.tests.util.xml import assert_xml_equal

from ..fixtures import _get_template_renderer, case_search_fixture_generator


class TestCaseSearchFixtures(TestCase):
    domain_name = 'test-case-search-fixtures'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain_name)
        cls.user = WebUser.create(cls.domain_name, 'test@dimagi.com', 'secret', None, None, is_admin=True)
        cls.restore_user = cls.user.to_ota_restore_user(cls.domain_name)
        cls.addClassCleanup(cls.domain_obj.delete)

    def render(self, template_string):
        return _get_template_renderer(self.restore_user).render(template_string)

    def test_no_interpolation(self):
        res = self.render("dob < '2020-01-01'")
        self.assertEqual(res, "dob < '2020-01-01'")

    def test_user_id(self):
        res = self.render("@owner_id = '{user.uuid}'")
        self.assertEqual(res, f"@owner_id = '{self.user.user_id}'")

    @patch('corehq.apps.case_search.fixtures._get_indicators')
    @patch('corehq.apps.case_search.fixtures._run_query')
    def test_fixture_generator(self, run_query, get_indicators):
        run_query.return_value = "42"
        get_indicators.return_value = [
            ('pre_pandemic_births', "dob < '2020-01-01'"),
            ('owned_by_user', "@owner_id = '{user.uuid}'"),
        ]
        res = call_fixture_generator(case_search_fixture_generator, self.restore_user, self.domain_obj)

        expected = """
        <fixture id="case-search-fixture">
           <values>
               <value name="pre_pandemic_births">42</value>
               <value name="owned_by_user">42</value>
           </values>
        </fixture>"""
        assert_xml_equal(expected, etree.tostring(res, encoding='utf-8'))
