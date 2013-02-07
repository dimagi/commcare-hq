from django.test import TestCase
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from datetime import datetime, timedelta
from copy import copy
from casexml.apps.case.tests.util import post_util

class CaseRebuildTest(TestCase):

    def setUp(self):
        for item in CommCareCase.view("case/by_user", include_docs=True, reduce=False).all():
            item.delete()

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
        copy = CommCareCaseAction.wrap(orig._doc)
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
        case_id = post_util(create=True)
        post_util(case_id=case_id, p1='p1-1', p2='p2-1')
        post_util(case_id=case_id, p2='p2-2', p3='p3-2')

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
        case.rebuild()
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-1') # updated (back!)
        self.assertEqual(case.p3, 'p3-2') # new

    def testReconcileActions(self):
        case_id = post_util(create=True)
        post_util(case_id=case_id, p1='p1-1', p2='p2-1')
        post_util(case_id=case_id, p2='p2-2', p3='p3-2')
        case = CommCareCase.get(case_id)

        # make sure we timestamp everything so they have the right order
        now = datetime.utcnow()
        for i, a in enumerate(case.actions):
            a.server_date = now + timedelta(seconds=i)

        original_actions = [copy(a) for a in case.actions]
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

