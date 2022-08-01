import uuid
from datetime import datetime, timedelta

from django.test import TestCase

from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import primary_actions
from corehq.apps.change_feed import topics
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.models import CommCareCase, RebuildWithReason, XFormInstance
from corehq.form_processor.tests.utils import sharded
from testapps.test_pillowtop.utils import capture_kafka_changes_context

REBUILD_TEST_DOMAIN = 'rebuild-test'


def _post_util(create=False, case_id=None, user_id=None, owner_id=None,
              case_type=None, submission_extras=None, close=False, date_modified=None,
              **kwargs):

    def uid():
        return uuid.uuid4().hex
    case_id = case_id or uid()
    block = CaseBlock(create=create,
                      case_id=case_id,
                      user_id=user_id or uid(),
                      owner_id=owner_id or uid(),
                      case_type=case_type or 'test',
                      date_modified=date_modified,
                      update=kwargs,
                      close=close)
    submit_case_blocks([block.as_text()], REBUILD_TEST_DOMAIN, submission_extras=submission_extras)
    return case_id


@sharded
class CaseRebuildTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(CaseRebuildTest, cls).setUpClass()
        delete_all_cases()

    def test_rebuild_empty(self):
        self.assertEqual(
            None,
            rebuild_case_from_forms('anydomain', 'notarealid', RebuildWithReason(reason='test'))
        )

    def _assertListEqual(self, l1, l2, include_ordering=True):
        if include_ordering:
            self.assertEqual(len(l1), len(l2))
            for i in range(len(l1)):
                self.assertEqual(l1[i], l2[i])
        else:
            # this is built in so just use it
            self.assertListEqual(l1, l2)

    def _assertListNotEqual(self, l1, l2, msg=None, include_ordering=True):
        try:
            self._assertListEqual(l1, l2, include_ordering=include_ordering)
        except self.failureException:
            pass  # this is what we want
        else:
            self.fail(msg)

    def test_archiving_only_form(self):
        """
        Checks that archiving the only form associated with the case archives
        the case and unarchiving unarchives it.
        """
        case_id = _post_util(create=True, p1='p1-1', p2='p2-1')
        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)

        self.assertFalse(case.is_deleted)
        self.assertEqual(1, len(case.actions))
        [form_id] = case.xform_ids
        form = XFormInstance.objects.get_form(form_id, REBUILD_TEST_DOMAIN)

        form.archive()
        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)

        self.assertTrue(case.is_deleted)
        # should just have the 'rebuild' action
        self.assertEqual(1, len(case.actions))
        self.assertTrue(case.actions[0].is_case_rebuild)

        form.unarchive()
        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)
        self.assertFalse(case.is_deleted)
        self.assertEqual(3, len(case.actions))
        self.assertTrue(case.actions[-1].is_case_rebuild)

    def test_form_archiving(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = _post_util(create=True, p1='p1-1', p2='p2-1',
                            submission_extras={'received_on': now})
        _post_util(case_id=case_id, p2='p2-2', p3='p3-2', p4='p4-2',
                  submission_extras={'received_on': now + timedelta(seconds=1)})
        _post_util(case_id=case_id, p4='p4-3', p5='p5-3', close=True,
                  submission_extras={'received_on': now + timedelta(seconds=2)})

        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)
        closed_by = case.closed_by
        closed_on = case.closed_on
        self.assertNotEqual('', closed_by)
        self.assertNotEqual(None, closed_on)

        def _check_initial_state(case):
            self.assertTrue(case.closed)
            self.assertEqual(closed_by, case.closed_by)
            self.assertEqual(closed_on, case.closed_on)
            self.assertEqual(case.get_case_property('p1'), 'p1-1')  # original
            self.assertEqual(case.get_case_property('p2'), 'p2-2')  # updated in second post
            self.assertEqual(case.get_case_property('p3'), 'p3-2')  # new in second post
            self.assertEqual(case.get_case_property('p4'), 'p4-3')  # updated in third post
            self.assertEqual(case.get_case_property('p5'), 'p5-3')  # new in third post
            # SQL stores one transaction per form
            self.assertEqual(3, len(primary_actions(case)))  # create + update + close

        _check_initial_state(case)

        # verify xform/action states
        [f1, f2, f3] = case.xform_ids
        [create, update, close] = case.actions
        self.assertEqual(f1, create.form_id)
        self.assertEqual(f2, update.form_id)
        self.assertEqual(f3, close.form_id)

        # todo: should this be the behavior for archiving the create form?
        get_form = XFormInstance.objects.get_form
        f1_doc = get_form(f1)
        with capture_kafka_changes_context(topics.CASE_SQL) as change_context:
            f1_doc.archive()

        self.assertEqual([case.case_id], [change.id for change in change_context.changes])

        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)

        self.assertEqual(2, len(primary_actions(case)))

        [u2, u3] = case.xform_ids
        self.assertEqual(f2, u2)
        self.assertEqual(f3, u3)

        self.assertTrue(case.closed)  # no change
        self.assertFalse('p1' in case.dynamic_case_properties())  # should disappear entirely
        self.assertEqual(case.get_case_property('p2'), 'p2-2')  # no change
        self.assertEqual(case.get_case_property('p3'), 'p3-2')  # no change
        self.assertEqual(case.get_case_property('p4'), 'p4-3')  # no change
        self.assertEqual(case.get_case_property('p5'), 'p5-3')  # no change

        def _reset(form_id):
            form_doc = get_form(form_id)
            form_doc.unarchive()
            case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)
            _check_initial_state(case)

        _reset(f1)

        f2_doc = get_form(f2)
        f2_doc.archive()
        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)

        self.assertEqual(2, len(primary_actions(case)))

        [u1, u3] = case.xform_ids
        self.assertEqual(f1, u1)
        self.assertEqual(f3, u3)

        self.assertTrue(case.closed)  # no change
        self.assertEqual(case.get_case_property('p1'), 'p1-1')  # original
        self.assertEqual(case.get_case_property('p2'), 'p2-1')  # loses second form update
        self.assertFalse('p3' in case.dynamic_case_properties())  # should disappear entirely
        self.assertEqual(case.get_case_property('p4'), 'p4-3')  # no change
        self.assertEqual(case.get_case_property('p5'), 'p5-3')  # no change

        _reset(f2)

        f3_doc = get_form(f3)
        f3_doc.archive()
        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)

        self.assertEqual(2, len(primary_actions(case)))

        [u1, u2] = case.xform_ids
        self.assertEqual(f1, u1)
        self.assertEqual(f2, u2)

        self.assertFalse(case.closed)  # reopened!
        self.assertEqual('', case.closed_by)
        self.assertEqual(None, case.closed_on)
        self.assertEqual(case.get_case_property('p1'), 'p1-1')  # original
        self.assertEqual(case.get_case_property('p2'), 'p2-2')  # original
        self.assertEqual(case.get_case_property('p3'), 'p3-2')  # new in second post
        self.assertEqual(case.get_case_property('p4'), 'p4-2')  # loses third form update
        self.assertFalse('p5' in case.dynamic_case_properties())  # should disappear entirely
        _reset(f3)

    def test_archie_modified_on(self):
        case_id = uuid.uuid4().hex
        now = datetime.utcnow().replace(microsecond=0)
        earlier = now - timedelta(hours=1)
        way_earlier = now - timedelta(days=1)
        # make sure we timestamp everything so they have the right order
        create_block = CaseBlock(case_id, create=True, date_modified=way_earlier)
        submit_case_blocks(
            [create_block.as_text()], 'test-domain', submission_extras={'received_on': way_earlier}
        )
        update_block = CaseBlock(case_id, update={'foo': 'bar'}, date_modified=earlier)
        submit_case_blocks(
            [update_block.as_text()], 'test-domain', submission_extras={'received_on': earlier}
        )

        case = CommCareCase.objects.get_case(case_id, 'test-domain')
        self.assertEqual(earlier, case.modified_on)

        second_form = XFormInstance.objects.get_form(case.xform_ids[-1], 'test-domain')
        second_form.archive()
        case = CommCareCase.objects.get_case(case_id, 'test-domain')
        self.assertEqual(way_earlier, case.modified_on)

    def test_archive_against_deleted_case(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = _post_util(create=True, p1='p1', submission_extras={'received_on': now})
        _post_util(case_id=case_id, p2='p2',
                  submission_extras={'received_on': now + timedelta(seconds=1)})
        _post_util(case_id=case_id, p3='p3',
                  submission_extras={'received_on': now + timedelta(seconds=2)})

        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)
        CommCareCase.objects.soft_delete_cases(REBUILD_TEST_DOMAIN, [case_id])

        [f1, f2, f3] = case.xform_ids
        f2_doc = XFormInstance.objects.get_form(f2, REBUILD_TEST_DOMAIN)
        f2_doc.archive()
        case = CommCareCase.objects.get_case(case_id, REBUILD_TEST_DOMAIN)
        self.assertTrue(case.is_deleted)

    def test_archive_removes_index(self):
        parent_case_id = uuid.uuid4().hex
        submit_case_blocks([
            CaseBlock(parent_case_id, create=True).as_text()
        ], 'test-domain')
        child_case_id = uuid.uuid4().hex
        submit_case_blocks([
            CaseBlock(child_case_id, create=True).as_text()
        ], 'test-domain')
        xform, _ = submit_case_blocks([
            CaseBlock(child_case_id, index={'mom': ('mother', parent_case_id)}).as_text()
        ], 'test-domain')

        case = CommCareCase.objects.get_case(child_case_id, 'test-domain')
        self.assertEqual(1, len(case.indices))

        xform.archive()

        case = CommCareCase.objects.get_case(child_case_id, 'test-domain')
        self.assertEqual(0, len(case.indices))
