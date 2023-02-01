from uuid import uuid4

import attr
from django.test import SimpleTestCase

from casexml.apps.case.const import CASE_ATTR_ID
from casexml.apps.case.xform import get_case_ids_from_form
from casexml.apps.case.xml import V2_NAMESPACE
from casexml.apps.case.xml.parser import XMLNS_ATTR


class TestXformCaseIds(SimpleTestCase):

    def test_basic(self):
        case_id = uuid4().hex
        xform = FakeForm({
            'data': {'some': 'stuff'},
            'case': case_block(case_id),
        })
        self.assertEqual(get_case_ids_from_form(xform), {case_id})

    def test_blocks_in_list(self):
        case_ids = {uuid4().hex for x in range(3)}
        xform = FakeForm({'data': {'parent': {'parent': {
            'case': [case_block(c) for c in case_ids]
        }}}})
        self.assertEqual(get_case_ids_from_form(xform), case_ids)

    def test_blocks_in_repeat(self):
        case_ids = {uuid4().hex for x in range(3)}
        blocks = [case_block(c) for c in case_ids]
        xform = FakeForm({
            'data': {
                'parent': {
                    'repeats': [{'group': {'case': block}} for block in blocks]
                }
            }
        })
        self.assertEqual(get_case_ids_from_form(xform), case_ids)


def case_block(case_id):
    return {XMLNS_ATTR: V2_NAMESPACE, CASE_ATTR_ID: case_id}


@attr.s
class FakeForm:
    form_data = attr.ib()

    def get_xml_element(self):
        return []
