import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import post_case_blocks
from corehq.apps.es import CaseES
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.case import CasePillow
from corehq.util.context_managers import drop_connected_signals
from corehq.util.elastic import delete_es_index


class CasePillowTest(TestCase):

    domain = 'case-pillowtest-domain'

    def setUp(self):
        FormProcessorTestUtils.delete_all_cases()
        self.pillow = CasePillow()
        self.elasticsearch = self.pillow.get_es_new()
        delete_es_index(self.pillow.es_index)

    def tearDown(self):
        delete_es_index(self.pillow.es_index)

    def test_case_pillow_couch(self):
        # make a case
        case_id = uuid.uuid4().hex
        case_name = 'case-name-{}'.format(uuid.uuid4().hex)

        # this avoids having to deal with all the reminders code bootstrap
        with drop_connected_signals(case_post_save):
            form, cases = post_case_blocks(
                [
                    CaseBlock(
                        create=True,
                        case_id=case_id,
                        case_name=case_name,
                    ).as_xml()
                ], domain=self.domain
            )

        self.assertEqual(1, len(cases))

        self.pillow.process_changes(since=0, forever=False)
        self.elasticsearch.indices.refresh(self.pillow.es_index)

        results = CaseES().run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case_id, case_doc['_id'])
        self.assertEqual(case_name, case_doc['name'])
        cases[0].delete()
