import uuid
import os
from datetime import datetime, timedelta
from django.test import SimpleTestCase, TestCase
from django.template import Template, Context

from dimagi.utils.parsing import json_format_datetime

from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.util.test_utils import TestFileMixin
from corehq.form_processor.models import XFormInstance
from corehq.form_processor.tests.utils import create_form_for_test
from casexml.apps.case.tests.util import delete_all_xforms
from casexml.apps.case.const import CASE_ATTR_ID
from casexml.apps.case.xform import extract_case_blocks, TempCaseBlockCache


CREATE_XFORM_ID = "6RGAZTETE3Z2QC0PE2DKM88MO"
TEST_DOMAIN_NAME = 'test-domain'


class TestExtractCaseBlocks(SimpleTestCase):

    def test_basic(self):
        block = {CASE_ATTR_ID: uuid.uuid4().hex}
        blocks = extract_case_blocks({
            'data': {
                'some': 'stuff'
            },
            'case': block
        })
        self.assertEqual(1, len(blocks))
        self.assertEqual(block, blocks[0])

    def test_simple_path(self):
        block = {CASE_ATTR_ID: uuid.uuid4().hex}
        block_with_path = extract_case_blocks({
            'data': {
                'some': 'stuff'
            },
            'case': block
        }, include_path=True)[0]
        self.assertEqual(block, block_with_path.caseblock)
        self.assertEqual([], block_with_path.path)

    def test_nested_path(self):
        block = {CASE_ATTR_ID: uuid.uuid4().hex}
        blocks = extract_case_blocks({
            'data': {
                'parents': {
                    'parent': {
                        'case': block
                    }
                }

            }
        }, include_path=True)
        self.assertEqual(1, len(blocks))
        self.assertEqual(block, blocks[0].caseblock)
        self.assertEqual(['data', 'parents', 'parent'], blocks[0].path)

    def test_blocks_in_list(self):
        blocks = [{CASE_ATTR_ID: uuid.uuid4().hex} for i in range(3)]
        blocks_back = extract_case_blocks({
            'data': {
                'parent': {
                    'parent': {
                        'case': blocks
                    }
                }

            }
        }, include_path=True)
        self.assertEqual(3, len(blocks))
        for i in range(len(blocks)):
            self.assertEqual(blocks[i], blocks_back[i].caseblock)
            self.assertEqual(['data', 'parent', 'parent'], blocks_back[i].path)

    def test_blocks_in_repeat(self):
        blocks = [{CASE_ATTR_ID: uuid.uuid4().hex} for i in range(3)]
        repeats = [{'group': {'case': block}} for block in blocks]
        blocks_back = extract_case_blocks({
            'data': {
                'parent': {
                    'repeats': repeats
                }
            }
        }, include_path=True)
        self.assertEqual(3, len(blocks))
        for i in range(len(blocks)):
            self.assertEqual(blocks[i], blocks_back[i].caseblock)
            self.assertEqual(['data', 'parent', 'repeats', 'group'], blocks_back[i].path)


class TempCaseBlockCacheTests(TestCase):
    def setUp(self):
        self.domain = 'test_case_block_cache'
        self.form_id = '1234'

    def test_no_db_hit_if_cached(self):
        cache_obj = TempCaseBlockCache()
        blocks = extract_case_blocks({
            'data': {
                'some': 'stuff'
            },
            'case': {CASE_ATTR_ID: uuid.uuid4().hex}
        })
        cache_obj.cache[self.form_id] = blocks
        block_form = create_form_for_test(self.domain, form_id=self.form_id)
        retrieved_blocks = cache_obj.get_case_blocks(block_form)
        self.assertEqual(retrieved_blocks, blocks)

    def test_extracts_case_blocks_if_not_cached(self):
        cache_obj = TempCaseBlockCache()
        block_form = create_form_for_test(self.domain, form_id=self.form_id)
        retrieved_blocks = cache_obj.get_case_blocks(block_form)
        self.assertEqual(retrieved_blocks, [])  # test form has no case blocks

    def test_caches_case_blocks_if_not_cached(self):
        cache_obj = TempCaseBlockCache()
        block_form = create_form_for_test(self.domain, form_id=self.form_id)
        cache_obj.get_case_blocks(block_form)
        self.assertEqual(cache_obj.cache[self.form_id], [])  # test form has no case blocks


class TestParsingExtractCaseBlock(TestCase, TestFileMixin):
    file_path = ('./', 'data')
    root = os.path.dirname(__file__)

    def setUp(self):
        delete_all_xforms()

    def _formatXForm(self, doc_id, raw_xml, attachment_block, date=None):
        if date is None:
            date = datetime.utcnow()
        final_xml = Template(raw_xml.decode("utf8")).render(Context({
            "attachments": attachment_block,
            "time_start": json_format_datetime(date - timedelta(minutes=4)),
            "time_end": json_format_datetime(date),
            "date_modified": json_format_datetime(date),
            "doc_id": doc_id
        })).encode("utf8")
        return final_xml

    def test_parsing_date_modified(self):
        """
        To ensure that extract_case_blocks processes date_modified when passed
        as datetime.datetime object using XFormInstance.objects.get_form and
        form_data when at validate_phone_datetime
        """
        xml_data = self.get_xml('create')
        final_xml = self._formatXForm(CREATE_XFORM_ID, xml_data, {})
        result = submit_form_locally(
            final_xml,
            TEST_DOMAIN_NAME,
            attachments={},
            last_sync_token=None,
            received_on=None
        )
        xform = XFormInstance.objects.get_form(result.xform.get_id, TEST_DOMAIN_NAME)
        extract_case_blocks(xform.form_data)
