import uuid
from collections import namedtuple
from unittest.mock import call, patch

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.bulk import (
    SystemFormMeta,
    case_block_submitter,
    update_cases,
)
from corehq.apps.hqcase.utils import CASEBLOCK_CHUNKSIZE
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class TestUpdateCases(TestCase):
    domain = 'test_bulk_update_cases'

    def tearDown(self):
        FormProcessorTestUtils.delete_all_xforms()
        FormProcessorTestUtils.delete_all_cases()
        super().tearDown()

    def test(self):
        case_ids = [str(uuid.uuid4()) for i in range(1, 18)]

        form_meta = SystemFormMeta()
        with case_block_submitter(
            self.domain,
            device_id=form_meta.device_id,
            user_id=form_meta.user_id,
            username=form_meta.username,
            chunk_size=5,
        ) as submitter:
            for i, case_id in enumerate(case_ids):
                case_block = CaseBlock(
                    create=True,
                    case_id=case_id,
                    case_type='patient',
                    case_name=f"case_{i}",
                    update={
                        'phase': '1',
                        'to_update': 'yes' if i % 2 else 'no',
                    },
                )
                submitter.send(case_block)

        self.assertEqual(len(XFormInstance.objects.get_form_ids_in_domain(self.domain)), 4)
        self.assertEqual(len(CommCareCase.objects.get_case_ids_in_domain(self.domain)), len(case_ids))

        update_cases(self.domain, _set_phase_2, case_ids)

        for case in CommCareCase.objects.get_cases(case_ids):
            correct_phase = '2' if case.get_case_property('to_update') == 'yes' else '1'
            self.assertEqual(case.get_case_property('phase'), correct_phase)


def _set_phase_2(case):
    if case.get_case_property('to_update') == 'yes':
        return [CaseBlock(
            case_id=case.case_id,
            update={'phase': '2'},
        )]


def test_case_block_submitter():
    FakeXForm = namedtuple('FakeXForm', 'form_id')
    with patch('corehq.apps.hqcase.bulk.submit_case_blocks') as mock_submit:
        mock_submit.return_value = (FakeXForm(('form_id',)), ['cases'])

        with case_block_submitter(
            'test-domain',
            username='test-user',
        ) as submitter:
            # Send enough to trigger one chunk, then one more for a
            # second chunk on close
            for i in range(CASEBLOCK_CHUNKSIZE + 1):
                submitter.send(f'case_block_{i}')

            assert mock_submit.call_count == 1
            assert len(mock_submit.call_args[0][0]) == CASEBLOCK_CHUNKSIZE

        assert mock_submit.call_count == 2
        assert mock_submit.call_args == call(
            [f'case_block_{CASEBLOCK_CHUNKSIZE}'],
            'test-domain',
            username='test-user'
        )
