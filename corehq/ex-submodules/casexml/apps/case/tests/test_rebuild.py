import uuid
from couchdbkit.exceptions import ResourceNotFound
from django.test import TestCase, SimpleTestCase
from casexml.apps.case import const
from casexml.apps.case.cleanup import rebuild_case
from casexml.apps.case.exceptions import MissingServerDate
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase, CommCareCaseAction, _action_sort_key_function
from datetime import datetime, timedelta
from copy import deepcopy
from casexml.apps.case.tests.util import post_util as real_post_util, delete_all_cases
from casexml.apps.case.util import primary_actions, post_case_blocks
from couchforms.models import XFormInstance
from dimagi.utils.parsing import json_format_datetime


def post_util(**kwargs):
    form_extras = kwargs.get('form_extras', {})
    form_extras['domain'] = 'rebuild-test'
    kwargs['form_extras'] = form_extras
    return real_post_util(**kwargs)


class CaseRebuildTest(TestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_cases()

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
            pass # this is what we want
        else:
            self.fail(msg)

    def testActionEquality(self):
        case_id = post_util(create=True)
        post_util(case_id=case_id, p1='p1', p2='p2')

        case = CommCareCase.get(case_id)
        self.assertEqual(2, len(case.actions)) # create + update
        self.assertTrue(case.actions[0] != case.actions[1])
        self.assertTrue(case.actions[1] == case.actions[1])

        orig = case.actions[1]
        copy = CommCareCaseAction.wrap(orig._doc.copy())
        self.assertTrue(copy != case.actions[0])
        self.assertTrue(copy == orig)

        copy.server_date = copy.server_date + timedelta(seconds=1)
        self.assertTrue(copy != orig)
        copy.server_date = orig.server_date
        self.assertTrue(copy == orig)

        copy.updated_unknown_properties['p1'] = 'not-p1'
        self.assertTrue(copy != orig)
        copy.updated_unknown_properties['p1'] = 'p1'
        self.assertTrue(copy == orig)
        copy.updated_unknown_properties['pnew'] = ''
        self.assertTrue(copy != orig)

    def testBasicRebuild(self):
        user_id = 'test-basic-rebuild-user'
        case_id = post_util(create=True, user_id=user_id)
        post_util(case_id=case_id, p1='p1-1', p2='p2-1', user_id=user_id)
        post_util(case_id=case_id, p2='p2-2', p3='p3-2', user_id=user_id)

        # check initial state
        case = CommCareCase.get(case_id)
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-2') # updated
        self.assertEqual(case.p3, 'p3-2') # new
        self.assertEqual(3, len(case.actions)) # create + 2 updates
        a1 = case.actions[1]
        self.assertEqual(a1.updated_unknown_properties['p1'], 'p1-1')
        self.assertEqual(a1.updated_unknown_properties['p2'], 'p2-1')
        a2 = case.actions[2]
        self.assertEqual(a2.updated_unknown_properties['p2'], 'p2-2')
        self.assertEqual(a2.updated_unknown_properties['p3'], 'p3-2')

        # rebuild by flipping the actions
        case.actions = [case.actions[0], a2, a1]
        case.xform_ids = [case.xform_ids[0], case.xform_ids[2], case.xform_ids[1]]
        case.rebuild()
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-2') # updated (back!)
        self.assertEqual(case.p3, 'p3-2') # new

    def testActionComparison(self):
        user_id = 'test-action-comparison-user'
        case_id = post_util(create=True, property='a1 wins', user_id=user_id)
        post_util(case_id=case_id, property='a2 wins', user_id=user_id)
        post_util(case_id=case_id, property='a3 wins', user_id=user_id)

        # check initial state
        case = CommCareCase.get(case_id)
        create, a1, a2, a3 = deepcopy(list(case.actions))
        self.assertEqual('a3 wins', case.property)
        self.assertEqual(a1.updated_unknown_properties['property'], 'a1 wins')
        self.assertEqual(a2.updated_unknown_properties['property'], 'a2 wins')
        self.assertEqual(a3.updated_unknown_properties['property'], 'a3 wins')

        def _confirm_action_order(case, expected_actions):
            actual_actions = case.actions[1:]  # always assume create is first and removed
            for expected, actual in zip(expected_actions, actual_actions):
                self.assertEqual(expected.updated_unknown_properties['property'],
                                 actual.updated_unknown_properties['property'])

        _confirm_action_order(case, [a1, a2, a3])

        # test initial rebuild does nothing
        case.rebuild()
        _confirm_action_order(case, [a1, a2, a3])

        # test sorting by server date
        case.actions[2].server_date = case.actions[2].server_date + timedelta(days=1)
        case.rebuild()
        _confirm_action_order(case, [a1, a3, a2])

        # test sorting by date within the same day
        case = CommCareCase.get(case_id)
        _confirm_action_order(case, [a1, a2, a3])
        case.actions[2].date = case.actions[3].date + timedelta(minutes=1)
        case.rebuild()
        _confirm_action_order(case, [a1, a3, a2])

        # test original form order
        case = CommCareCase.get(case_id)
        case.actions[3].server_date = case.actions[2].server_date
        case.actions[3].date = case.actions[2].date
        case.xform_ids = [a1.xform_id, a3.xform_id, a2.xform_id]
        case.rebuild()
        _confirm_action_order(case, [a1, a3, a2])

        # test create comes before update
        case = CommCareCase.get(case_id)
        case.actions = [a1, create, a2, a3]
        case.rebuild()
        _confirm_action_order(case, [a1, a2, a3])

    def testRebuildEmpty(self):
        self.assertEqual(None, rebuild_case('notarealid'))
        try:
            CommCareCase.get_with_rebuild('notarealid')
            self.fail('get with rebuild should still fail for unknown cases')
        except ResourceNotFound:
            pass

    def testRebuildCreateCase(self):
        case_id = post_util(create=True)
        post_util(case_id=case_id, p1='p1', p2='p2')

        # delete initial case
        case = CommCareCase.get(case_id)
        case.delete()

        case = rebuild_case(case_id)
        self.assertEqual(case.p1, 'p1')
        self.assertEqual(case.p2, 'p2')
        self.assertEqual(2, len(primary_actions(case)))  # create + update

        case.delete()
        try:
            CommCareCase.get(case_id)
            self.fail('get should fail on deleted cases')
        except ResourceNotFound:
            pass

        case = CommCareCase.get_with_rebuild(case_id)
        self.assertEqual(case.p1, 'p1')
        self.assertEqual(case.p2, 'p2')

    def testReconcileActions(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = post_util(create=True, form_extras={'received_on': now})
        post_util(case_id=case_id, p1='p1-1', p2='p2-1', form_extras={'received_on': now + timedelta(seconds=1)})
        post_util(case_id=case_id, p2='p2-2', p3='p3-2', form_extras={'received_on': now + timedelta(seconds=2)})
        case = CommCareCase.get(case_id)

        original_actions = [deepcopy(a) for a in case.actions]
        original_form_ids = [id for id in case.xform_ids]
        self.assertEqual(3, len(original_actions))
        self.assertEqual(3, len(original_form_ids))
        self._assertListEqual(original_actions, case.actions)

        # test reordering
        case.actions = [case.actions[2], case.actions[1], case.actions[0]]
        self._assertListNotEqual(original_actions, case.actions)
        case.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)

        # test duplication
        case.actions = case.actions * 3
        self.assertEqual(9, len(case.actions))
        self._assertListNotEqual(original_actions, case.actions)
        case.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)

        # test duplication, even when dates are off
        case.actions = original_actions + [deepcopy(case.actions[2])]
        case.actions[-1].server_date = case.actions[-1].server_date + timedelta(seconds=1)
        self._assertListNotEqual(original_actions, case.actions)
        case.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)

        # test duplication with different properties is actually
        # treated differently
        case.actions = original_actions + [deepcopy(case.actions[2])]
        case.actions[-1].updated_unknown_properties['new'] = 'mismatch'
        self.assertEqual(4, len(case.actions))
        self._assertListNotEqual(original_actions, case.actions)
        case.reconcile_actions()
        self._assertListNotEqual(original_actions, case.actions)

        # test clean slate rebuild
        case = rebuild_case(case_id)
        self._assertListEqual(original_actions, primary_actions(case))
        self._assertListEqual(original_form_ids, case.xform_ids)

    def testArchivingOnlyForm(self):
        """
        Checks that archiving the only form associated with the case archives
        the case and unarchiving unarchives it.
        """
        case_id = post_util(create=True, p1='p1-1', p2='p2-1')
        case = CommCareCase.get(case_id)

        self.assertEqual('CommCareCase', case._doc['doc_type'])
        self.assertEqual(2, len(case.actions))
        [form_id] = case.xform_ids
        form = XFormInstance.get(form_id)

        form.archive()
        case = CommCareCase.get(case_id)

        self.assertEqual('CommCareCase-Deleted', case._doc['doc_type'])
        # should just have the 'rebuild' action
        self.assertEqual(1, len(case.actions))
        self.assertEqual(const.CASE_ACTION_REBUILD, case.actions[0].action_type)

        form.unarchive()
        case = CommCareCase.get(case_id)
        self.assertEqual('CommCareCase', case._doc['doc_type'])
        self.assertEqual(3, len(case.actions))
        self.assertEqual(const.CASE_ACTION_REBUILD, case.actions[-1].action_type)

    def testFormArchiving(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = post_util(create=True, p1='p1-1', p2='p2-1',
                            form_extras={'received_on': now})
        post_util(case_id=case_id, p2='p2-2', p3='p3-2', p4='p4-2',
                  form_extras={'received_on': now + timedelta(seconds=1)})
        post_util(case_id=case_id, p4='p4-3', p5='p5-3', close=True,
                  form_extras={'received_on': now + timedelta(seconds=2)})

        case = CommCareCase.get(case_id)
        closed_by = case.closed_by
        closed_on = case.closed_on
        self.assertNotEqual('', closed_by)
        self.assertNotEqual(None, closed_on)

        def _check_initial_state(case):
            self.assertTrue(case.closed)
            self.assertEqual(closed_by, case.closed_by)
            self.assertEqual(closed_on, case.closed_on)
            self.assertEqual(case.p1, 'p1-1')  # original
            self.assertEqual(case.p2, 'p2-2')  # updated in second post
            self.assertEqual(case.p3, 'p3-2')  # new in second post
            self.assertEqual(case.p4, 'p4-3')  # updated in third post
            self.assertEqual(case.p5, 'p5-3')  # new in third post
            self.assertEqual(5, len(primary_actions(case)))  # create + 3 updates + close

        _check_initial_state(case)

        # verify xform/action states
        [create, u1, u2, u3, close] = case.actions
        [f1, f2, f3] = case.xform_ids
        self.assertEqual(f1, create.xform_id)
        self.assertEqual(f1, u1.xform_id)
        self.assertEqual(f2, u2.xform_id)
        self.assertEqual(f3, u3.xform_id)

        # todo: should this be the behavior for archiving the create form?
        f1_doc = XFormInstance.get(f1)
        f1_doc.archive()
        case = CommCareCase.get(case_id)

        self.assertEqual(3, len(primary_actions(case)))
        [u2, u3] = case.xform_ids
        self.assertEqual(f2, u2)
        self.assertEqual(f3, u3)

        self.assertTrue(case.closed)  # no change
        self.assertFalse('p1' in case._doc)  # should disappear entirely
        self.assertEqual(case.p2, 'p2-2')  # no change
        self.assertEqual(case.p3, 'p3-2')  # no change
        self.assertEqual(case.p4, 'p4-3')  # no change
        self.assertEqual(case.p5, 'p5-3')  # no change

        def _reset(form_id):
            form_doc = XFormInstance.get(form_id)
            form_doc.unarchive()
            case = CommCareCase.get(case_id)
            _check_initial_state(case)

        _reset(f1)

        f2_doc = XFormInstance.get(f2)
        f2_doc.archive()
        case = CommCareCase.get(case_id)

        self.assertEqual(4, len(primary_actions(case)))
        [u1, u3] = case.xform_ids
        self.assertEqual(f1, u1)
        self.assertEqual(f3, u3)

        self.assertTrue(case.closed) # no change
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-1') # loses second form update
        # self.assertFalse('p3' in case._doc) # todo: should disappear entirely
        self.assertEqual(case.p4, 'p4-3') # no change
        self.assertEqual(case.p5, 'p5-3') # no change

        _reset(f2)

        f3_doc = XFormInstance.get(f3)
        f3_doc.archive()
        case = CommCareCase.get(case_id)

        self.assertEqual(3, len(primary_actions(case)))
        [u1, u2] = case.xform_ids
        self.assertEqual(f1, u1)
        self.assertEqual(f2, u2)

        self.assertFalse(case.closed)  # reopened!
        self.assertEqual('', case.closed_by)
        self.assertEqual(None, case.closed_on)
        self.assertEqual(case.p1, 'p1-1')  # original
        self.assertEqual(case.p2, 'p2-2')  # original
        self.assertEqual(case.p3, 'p3-2')  # new in second post
        self.assertEqual(case.p4, 'p4-2')  # loses third form update
        # self.assertFalse('p5' in case._doc) # todo: should disappear entirely
        _reset(f3)

    def testArchiveModifiedOn(self):
        case_id = uuid.uuid4().hex
        now = datetime.utcnow().replace(microsecond=0)
        earlier = now - timedelta(hours=1)
        way_earlier = now - timedelta(days=1)
        # make sure we timestamp everything so they have the right order
        create_block = CaseBlock(case_id, create=True, date_modified=way_earlier)
        post_case_blocks([create_block.as_xml(json_format_datetime)], form_extras={'received_on': way_earlier})
        update_block = CaseBlock(case_id, update={'foo': 'bar'}, date_modified=earlier)
        post_case_blocks([update_block.as_xml(json_format_datetime)], form_extras={'received_on': earlier})

        case = CommCareCase.get(case_id)
        self.assertEqual(earlier, case.modified_on)

        second_form = XFormInstance.get(case.xform_ids[-1])
        second_form.archive()
        case = CommCareCase.get(case_id)
        self.assertEqual(way_earlier, case.modified_on)

    def testArchiveAgainstDeletedCases(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = post_util(create=True, p1='p1', form_extras={'received_on': now})
        post_util(case_id=case_id, p2='p2',
                  form_extras={'received_on': now + timedelta(seconds=1)})
        post_util(case_id=case_id, p3='p3',
                  form_extras={'received_on': now + timedelta(seconds=2)})

        case = CommCareCase.get(case_id)
        case.doc_type = 'CommCareCase-Deleted'
        case.save()

        [f1, f2, f3] = case.xform_ids
        f2_doc = XFormInstance.get(f2)
        f2_doc.archive()
        case = CommCareCase.get(case_id)
        self.assertEqual(case.doc_type, 'CommCareCase-Deleted')


class TestCheckActionOrder(SimpleTestCase):

    def test_already_sorted(self):
        case = CommCareCase(actions=[
            CommCareCaseAction(server_date=datetime(2001, 1, 1, 0, 0, 0)),
            CommCareCaseAction(server_date=datetime(2001, 1, 2, 0, 0, 0)),
            CommCareCaseAction(server_date=datetime(2001, 1, 3, 0, 0, 0)),
        ])
        self.assertTrue(case.check_action_order())

    def test_out_of_order(self):
        case = CommCareCase(actions=[
            CommCareCaseAction(server_date=datetime(2001, 1, 1, 0, 0, 0)),
            CommCareCaseAction(server_date=datetime(2001, 1, 3, 0, 0, 0)),
            CommCareCaseAction(server_date=datetime(2001, 1, 2, 0, 0, 0)),
        ])
        self.assertFalse(case.check_action_order())

    def test_sorted_with_none(self):
        case = CommCareCase(actions=[
            CommCareCaseAction(server_date=datetime(2001, 1, 1, 0, 0, 0)),
            CommCareCaseAction(server_date=None),
            CommCareCaseAction(server_date=datetime(2001, 1, 2, 0, 0, 0)),
            CommCareCaseAction(server_date=datetime(2001, 1, 3, 0, 0, 0)),
        ])
        self.assertTrue(case.check_action_order())

    def test_out_of_order_with_none(self):
        case = CommCareCase(actions=[
            CommCareCaseAction(server_date=datetime(2001, 1, 1, 0, 0, 0)),
            CommCareCaseAction(server_date=datetime(2001, 1, 3, 0, 0, 0)),
            CommCareCaseAction(server_date=None),
            CommCareCaseAction(server_date=datetime(2001, 1, 2, 0, 0, 0)),
        ])
        self.assertFalse(case.check_action_order())


class TestActionSortKey(SimpleTestCase):

    def test_missing_server_date(self):
        case = CommCareCase(actions=[
            _make_action(server_date=datetime(2001, 1, 1)),
            _make_action(server_date=None, phone_date=datetime(2001, 1, 1)),
        ])
        with self.assertRaises(MissingServerDate):
            sorted(case.actions, key=_action_sort_key_function(case))

    def test_missing_phone_date(self):
        case = CommCareCase(actions=[
            _make_action(server_date=datetime(2001, 1, 1)),
            _make_action(server_date=datetime(2001, 1, 1), phone_date=None),
        ])
        with self.assertRaises(MissingServerDate):
            sorted(case.actions, key=_action_sort_key_function(case))

    def test_sort_by_server_date(self):
        expected_actions = (
            (0, _make_action(server_date=datetime(2001, 1, 1))),
            (2, _make_action(server_date=datetime(2001, 1, 3))),
            (1, _make_action(server_date=datetime(2001, 1, 2))),
        )
        self._test(expected_actions)

    def test_sort_by_server_date_precise(self):
        expected_actions = (
            (1, _make_action(server_date=datetime(2001, 1, 1, 0, 0, 1))),
            (0, _make_action(server_date=datetime(2001, 1, 1, 0, 0, 0))),
        )
        self._test(expected_actions)

    def test_default_to_phone_date_on_same_day(self):
        expected_actions = (
            (1, _make_action(server_date=datetime(2001, 1, 1, 0, 0, 0), phone_date=datetime(2001, 1, 1, 0, 0, 1))),
            (0, _make_action(server_date=datetime(2001, 1, 1, 0, 0, 1), phone_date=datetime(2001, 1, 1, 0, 0, 0))),
        )
        self._test(expected_actions)

    def test_create_before_update(self):
        expected_actions = (
            (1, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_UPDATE)),
            (0, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_CREATE)),
        )
        self._test(expected_actions)

    def test_update_before_close(self):
        expected_actions = (
            (1, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_CLOSE)),
            (0, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_UPDATE)),
        )
        self._test(expected_actions)

    def test_different_usernames_default_to_server_date(self):
        expected_actions = (
            (0, _make_action(server_date=datetime(2001, 1, 1, 0, 0, 0),
                             phone_date=datetime(2001, 1, 1, 0, 0, 1),
                             user_id='user1')),
            (1, _make_action(server_date=datetime(2001, 1, 1, 0, 0, 1),
                             phone_date=datetime(2001, 1, 1, 0, 0, 0),
                             user_id='user2')),
        )
        self._test(expected_actions)

    def _test(self, action_tuples):
        """
        Takes in an iterable of tuples of the form: (expected_index, action).

        Calls the sort function on the actions in the order of the tuples and
        then asserts that they end up sorted in the order specified by the expected_index
        values.
        """
        case = CommCareCase(actions=[tup[1] for tup in action_tuples])
        sorted_actions = sorted(case.actions, key=_action_sort_key_function(case))
        for index, action in action_tuples:
            self.assertEqual(action, sorted_actions[index])

EMPTY_DATE = object()


def _make_action(server_date, phone_date=EMPTY_DATE, action_type=const.CASE_ACTION_UPDATE, user_id='someuserid'):
    if phone_date == EMPTY_DATE:
        phone_date = server_date
    return CommCareCaseAction(action_type=action_type, server_date=server_date, date=phone_date, user_id=user_id)
