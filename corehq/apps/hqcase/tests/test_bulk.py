import uuid
from collections import namedtuple
from unittest.mock import call, patch

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.bulk import (
    SystemFormMeta,
    submit_case_block_context,
    submit_case_block_coro,
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
        with submit_case_block_context(
            self.domain,
            device_id=form_meta.device_id,
            user_id=form_meta.user_id,
            username=form_meta.username,
            chunk_size=5,
        ) as submit_case_block:
            for i, case_id in enumerate(case_ids):
                submit_case_block.send(CaseBlock(
                    create=True,
                    case_id=case_id,
                    case_type='patient',
                    case_name=f"case_{i}",
                    update={
                        'phase': '1',
                        'to_update': 'yes' if i % 2 else 'no',
                    },
                ))

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


def test_submit_case_block_context():
    FakeXForm = namedtuple('FakeXForm', 'form_id')
    with patch('corehq.apps.hqcase.bulk.submit_case_blocks') as mock_submit:
        mock_submit.return_value = (FakeXForm(('form_id',)), ['cases'])

        with submit_case_block_context(
            'test-domain',
            username='test-user',
        ) as submit_case_block:
            # Send enough to trigger one chunk, then one more for a
            # second chunk on close
            for i in range(CASEBLOCK_CHUNKSIZE + 1):
                submit_case_block.send(f'case_block_{i}')

            assert mock_submit.call_count == 1
            assert len(mock_submit.call_args[0][0]) == CASEBLOCK_CHUNKSIZE

        assert mock_submit.call_count == 2
        assert mock_submit.call_args == call(
            [f'case_block_{CASEBLOCK_CHUNKSIZE}'],
            'test-domain',
            username='test-user'
        )


def test_submit_case_block_coro():
    FakeXForm = namedtuple('FakeXForm', 'form_id')
    with patch('corehq.apps.hqcase.bulk.submit_case_blocks') as mock_submit:
        mock_submit.side_effect = lambda blocks, *a, **kw: (
            FakeXForm((f'xform_{len(blocks)}',)),
            [f'case_{i}' for i in range(len(blocks))]
        )
        chunk_size = 10

        coro = submit_case_block_coro(
            'test-domain',
            username='test-user',
            chunk_size=chunk_size,
        )
        next(coro)  # Prime the coroutine

        # Send enough to trigger one chunk, then one more for a second
        # chunk on close
        for i in range(chunk_size + 1):
            coro.send(f'case_block_{i}')

        try:
            coro.send(None)  # Raises StopIteration on exit
        except StopIteration as exc:
            form_ids = exc.value
        # Use `coro.close()` instead of `coro.send(None)` if you don't
        # care about the return value.

        # First chunk: chunk_size; Second chunk: 1
        assert len(form_ids) == 2
        assert form_ids[0][0] == f'xform_{chunk_size}'
        assert form_ids[1][0] == 'xform_1'
        assert mock_submit.call_count == 2
