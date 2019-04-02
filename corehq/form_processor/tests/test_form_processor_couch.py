from __future__ import absolute_import
from __future__ import unicode_literals
import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.backends.couch.processor import FormProcessorCouch
from corehq.util.test_utils import generate_cases
from dimagi.utils.couch import release_lock


class TestFormProcessorCouch(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestFormProcessorCouch, cls).setUpClass()
        cls.case_id = uuid.uuid4().hex
        case = CaseBlock(
            create=True,
            case_id=cls.case_id,
            user_id='user1',
            owner_id='user1',
            case_type='demo',
            case_name='wrap?'
        )
        cls.domain = uuid.uuid4().hex

        cls.case = post_case_blocks([case.as_xml()], domain=cls.domain)[1][0]

    @classmethod
    def tearDownClass(cls):
        cls.case.delete()
        super(TestFormProcessorCouch, cls).tearDownClass()


@generate_cases([
    (True, True),
    (True, False),
    (False, True),
    (False, False),
], TestFormProcessorCouch)
def test_get_case_with_lock(self, lock, wrap):
    case, case_lock = FormProcessorCouch.get_case_with_lock(self.case_id, lock, wrap)

    try:
        if lock:
            self.assertIsNotNone(case_lock)
        else:
            self.assertIsNone(case_lock)

        if wrap:
            self.assertEqual(len(case.actions), 2)
        else:
            self.assertEqual('actions' in case, True)

        self.assertIsInstance(case, CommCareCase if wrap else dict)
    finally:
        release_lock(case_lock, True)
