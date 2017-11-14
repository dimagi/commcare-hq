from __future__ import absolute_import

import uuid

from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseBlock
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.integrations.utils import case_properties_changed


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class TestCasePropertiesChanged(TestCase):
    def setUp(self):
        self.domain = 'domain'
        create_domain(self.domain)
        case_type = "case"
        self.case_id = uuid.uuid4().hex
        submit_case_blocks(CaseBlock(
            self.case_id, case_type=case_type, create=True).as_string(), self.domain
        )
        caseblock1 = CaseBlock(
            self.case_id,
            case_type=case_type,
            update={'property_1': 'updated'},
        )
        caseblock2 = CaseBlock(
            self.case_id,
            case_type=case_type,
            update={'property_2': 'updated'},
        )
        blocks = [caseblock1.as_string(), caseblock2.as_string()]
        submit_case_blocks(blocks, self.domain)

    def test_case_properties_changed(self):
        case = CaseAccessors(self.domain).get_case(self.case_id)
        self.assertTrue(case_properties_changed(case, ['property_1', 'property_2']))
