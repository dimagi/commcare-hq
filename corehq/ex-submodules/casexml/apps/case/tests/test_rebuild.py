from __future__ import absolute_import
from __future__ import unicode_literals

import uuid
from copy import deepcopy
from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase
from six.moves import range, zip

from casexml.apps.case import const
from casexml.apps.case.cleanup import rebuild_case_from_forms
from casexml.apps.case.exceptions import MissingServerDate
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase, CommCareCaseAction
from casexml.apps.case.tests.util import delete_all_cases
from casexml.apps.case.util import post_case_blocks, primary_actions
from corehq.apps.change_feed import topics
from corehq.form_processor.backends.couch.update_strategy import CouchCaseUpdateStrategy, _action_sort_key_function
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.models import RebuildWithReason
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.form_processor.utils.general import should_use_sql_backend
from testapps.test_pillowtop.utils import capture_kafka_changes_context

REBUILD_TEST_DOMAIN = 'rebuild-test'


def _post_util(create=False, case_id=None, user_id=None, owner_id=None,
              case_type=None, form_extras=None, close=False, date_modified=None,
              **kwargs):

    form_extras = form_extras or {}
    form_extras['domain'] = REBUILD_TEST_DOMAIN

    uid = lambda: uuid.uuid4().hex
    case_id = case_id or uid()
    block = CaseBlock(create=create,
                      case_id=case_id,
                      user_id=user_id or uid(),
                      owner_id=owner_id or uid(),
                      case_type=case_type or 'test',
                      date_modified=date_modified,
                      update=kwargs,
                      close=close)
    block = block.as_xml()
    post_case_blocks([block], form_extras)
    return case_id


class CaseRebuildTestMixin(object):

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


class CouchCaseRebuildTest(TestCase, CaseRebuildTestMixin):

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        super(CouchCaseRebuildTest, cls).tearDownClass()

    def test_couch_action_equality(self):
        case_id = _post_util(create=True)
        _post_util(case_id=case_id, p1='p1', p2='p2')

        case = CommCareCase.get(case_id)
        self.assertEqual(3, len(case.actions))  # (1) create & (2) update date opened (3) update properties
        self.assertTrue(case.actions[0] != case.actions[1])
        self.assertTrue(case.actions[1] == case.actions[1])

        orig = case.actions[2]
        copy = CommCareCaseAction.wrap(deepcopy(orig._doc))
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

    def test_couch_action_not_equals(self):
        orig = CommCareCaseAction()
        copy = CommCareCaseAction.wrap(deepcopy(orig._doc))
        self.assertTrue(orig == copy)
        self.assertFalse(orig != copy)

    def test_couch_soft_rebuild(self):
        user_id = 'test-basic-rebuild-user'
        now = datetime.utcnow()
        case_id = _post_util(create=True, user_id=user_id, date_modified=now)
        _post_util(case_id=case_id, p1='p1-1', p2='p2-1', user_id=user_id, date_modified=now)
        _post_util(case_id=case_id, p2='p2-2', p3='p3-2', user_id=user_id, date_modified=now)

        # check initial state
        case = CommCareCase.get(case_id)
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-2') # updated
        self.assertEqual(case.p3, 'p3-2') # new
        self.assertEqual(4, len(case.actions)) # create + update (2 actions) + 2 updates
        a0 = case.actions[1]
        self.assertEqual(a0.updated_known_properties['opened_on'], case.opened_on.date())
        a1 = case.actions[2]
        self.assertEqual(a1.updated_unknown_properties['p1'], 'p1-1')
        self.assertEqual(a1.updated_unknown_properties['p2'], 'p2-1')
        a2 = case.actions[3]
        self.assertEqual(a2.updated_unknown_properties['p2'], 'p2-2')
        self.assertEqual(a2.updated_unknown_properties['p3'], 'p3-2')

        # rebuild by flipping the actions
        case.actions = [case.actions[0], a2, a1]
        case.xform_ids = [case.xform_ids[0], case.xform_ids[2], case.xform_ids[1]]
        CouchCaseUpdateStrategy(case).soft_rebuild_case()
        self.assertEqual(case.p1, 'p1-1') # original
        self.assertEqual(case.p2, 'p2-1') # updated (back!)
        self.assertEqual(case.p3, 'p3-2') # new

    def test_couch_action_comparison(self):
        user_id = 'test-action-comparison-user'
        case_id = _post_util(create=True, property='a1 wins', user_id=user_id)
        _post_util(case_id=case_id, property='a2 wins', user_id=user_id)
        _post_util(case_id=case_id, property='a3 wins', user_id=user_id)

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
        update_strategy = CouchCaseUpdateStrategy(case)
        update_strategy.soft_rebuild_case()
        _confirm_action_order(case, [a1, a2, a3])

        # test sorting by server date
        case.actions[2].server_date = case.actions[2].server_date + timedelta(days=1)
        update_strategy.soft_rebuild_case()
        _confirm_action_order(case, [a1, a3, a2])

        # test sorting by date within the same day
        case = CommCareCase.get(case_id)
        _confirm_action_order(case, [a1, a2, a3])
        case.actions[2].date = case.actions[3].date + timedelta(minutes=1)
        CouchCaseUpdateStrategy(case).soft_rebuild_case()
        _confirm_action_order(case, [a1, a3, a2])

        # test original form order
        case = CommCareCase.get(case_id)
        case.actions[3].server_date = case.actions[2].server_date
        case.actions[3].date = case.actions[2].date
        case.xform_ids = [a1.xform_id, a3.xform_id, a2.xform_id]
        CouchCaseUpdateStrategy(case).soft_rebuild_case()
        _confirm_action_order(case, [a1, a3, a2])

        # test create comes before update
        case = CommCareCase.get(case_id)
        case.actions = [a1, create, a2, a3]
        CouchCaseUpdateStrategy(case).soft_rebuild_case()
        _confirm_action_order(case, [a1, a2, a3])

    def test_couch_rebuild_deleted_case(self):
        # Note: Can't run this on SQL because if a case gets hard deleted then
        # there is no way to find out which forms created / updated it without
        # going through ALL the forms in the domain. ie. there is no SQL
        # equivalent to the "form_case_index/form_case_index" couch view

        case_id = _post_util(create=True)
        _post_util(case_id=case_id, p1='p1', p2='p2')

        # delete initial case
        delete_all_cases()

        with self.assertRaises(CaseNotFound):
            CaseAccessors(REBUILD_TEST_DOMAIN).get_case(case_id)

        case = rebuild_case_from_forms(REBUILD_TEST_DOMAIN, case_id, RebuildWithReason(reason='test'))
        self.assertEqual(case.p1, 'p1')
        self.assertEqual(case.p2, 'p2')
        self.assertEqual(3, len(primary_actions(case)))  # create + update

    def test_couch_reconcile_actions(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = _post_util(create=True, form_extras={'received_on': now})
        _post_util(case_id=case_id, p1='p1-1', p2='p2-1', form_extras={'received_on': now + timedelta(seconds=1)})
        _post_util(case_id=case_id, p2='p2-2', p3='p3-2', form_extras={'received_on': now + timedelta(seconds=2)})
        case = CommCareCase.get(case_id)
        update_strategy = CouchCaseUpdateStrategy(case)

        original_actions = [deepcopy(a) for a in case.actions]
        original_form_ids = [id for id in case.xform_ids]
        self.assertEqual(4, len(original_actions))
        self.assertEqual(3, len(original_form_ids))
        self._assertListEqual(original_actions, case.actions)

        # test reordering
        case.actions = [case.actions[3], case.actions[2], case.actions[1], case.actions[0]]
        self._assertListNotEqual(original_actions, case.actions)
        update_strategy.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)

        # test duplication
        case.actions = case.actions * 3
        self.assertEqual(12, len(case.actions))
        self._assertListNotEqual(original_actions, case.actions)
        update_strategy.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)

        # test duplication, even when dates are off
        case.actions = original_actions + [deepcopy(case.actions[2])]
        case.actions[-1].server_date = case.actions[-1].server_date + timedelta(seconds=1)
        self._assertListNotEqual(original_actions, case.actions)
        update_strategy.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)

        # test duplication with different properties is actually
        # treated differently
        case.actions = original_actions + [deepcopy(case.actions[2])]
        case.actions[-1].updated_unknown_properties['new'] = 'mismatch'
        self.assertEqual(5, len(case.actions))
        self._assertListNotEqual(original_actions, case.actions)
        update_strategy.reconcile_actions()
        self._assertListNotEqual(original_actions, case.actions)

        # test clean slate rebuild
        case = rebuild_case_from_forms(REBUILD_TEST_DOMAIN, case_id, RebuildWithReason(reason='test'))
        self._assertListEqual(original_actions, primary_actions(case))
        self._assertListEqual(original_form_ids, case.xform_ids)

    def test_couch_reconcile_actions_different_ordering(self):
        created_at = datetime(2017, 12, 2, 10, 23, 14)
        case_id = _post_util(create=True, form_extras={'received_on': created_at})

        # this case update is processed much later than the created date,
        # but the time on the phone (date_modified) is much before the time the server received it
        _post_util(
            case_id=case_id,
            p1='p1-1',
            date_modifed=datetime(2018, 1, 26, 20, 22, 20),
            form_extras={'received_on': datetime(2018, 2, 2, 8, 41, 53)}
        )

        # this case update was received by the server before the previous update
        # however the date_modified is after the previous updates
        _post_util(
            case_id=case_id,
            p2='p2-2',
            date_modifed=datetime(2018, 2, 2, 8, 40, 43),
            form_extras={'received_on': datetime(2018, 2, 2, 8, 41, 0)}
        )
        case = CommCareCase.get(case_id)

        update_strategy = CouchCaseUpdateStrategy(case)
        original_actions = [deepcopy(a) for a in case.actions]
        self._assertListEqual(original_actions, case.actions)

        # assert that the actions should not be reorder
        self.assertTrue(update_strategy.check_action_order())

        # assert that if a re-ordering is attempted, it results in the same output
        update_strategy.reconcile_actions()
        self._assertListEqual(original_actions, case.actions)


class CaseRebuildTest(TestCase, CaseRebuildTestMixin):

    @classmethod
    def setUpClass(cls):
        super(CaseRebuildTest, cls).setUpClass()
        delete_all_cases()

    def test_rebuild_empty(self):
        self.assertEqual(
            None,
            rebuild_case_from_forms('anydomain', 'notarealid', RebuildWithReason(reason='test'))
        )

    def test_archiving_only_form(self):
        """
        Checks that archiving the only form associated with the case archives
        the case and unarchiving unarchives it.
        """
        case_id = _post_util(create=True, p1='p1-1', p2='p2-1')
        case_accessors = CaseAccessors(REBUILD_TEST_DOMAIN)
        case = case_accessors.get_case(case_id)

        self.assertFalse(case.is_deleted)
        if should_use_sql_backend(REBUILD_TEST_DOMAIN):
            self.assertEqual(1, len(case.actions))
        else:
            self.assertEqual(2, len(case.actions))
        [form_id] = case.xform_ids
        form = FormAccessors(REBUILD_TEST_DOMAIN).get_form(form_id)

        form.archive()
        case = case_accessors.get_case(case_id)

        self.assertTrue(case.is_deleted)
        # should just have the 'rebuild' action
        self.assertEqual(1, len(case.actions))
        self.assertTrue(case.actions[0].is_case_rebuild)

        form.unarchive()
        case = case_accessors.get_case(case_id)
        self.assertFalse(case.is_deleted)
        self.assertEqual(3, len(case.actions))
        self.assertTrue(case.actions[-1].is_case_rebuild)

    def test_form_archiving(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = _post_util(create=True, p1='p1-1', p2='p2-1',
                            form_extras={'received_on': now})
        _post_util(case_id=case_id, p2='p2-2', p3='p3-2', p4='p4-2',
                  form_extras={'received_on': now + timedelta(seconds=1)})
        _post_util(case_id=case_id, p4='p4-3', p5='p5-3', close=True,
                  form_extras={'received_on': now + timedelta(seconds=2)})

        case_accessors = CaseAccessors(REBUILD_TEST_DOMAIN)
        case = case_accessors.get_case(case_id)
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
            if should_use_sql_backend(REBUILD_TEST_DOMAIN):
                # SQL stores one transaction per form
                self.assertEqual(3, len(primary_actions(case)))  # create + update + close
            else:
                self.assertEqual(5, len(primary_actions(case)))  # create + 3 updates + close

        _check_initial_state(case)

        # verify xform/action states
        [f1, f2, f3] = case.xform_ids
        if should_use_sql_backend(REBUILD_TEST_DOMAIN):
            [create, update, close] = case.actions
            self.assertEqual(f1, create.form_id)
            self.assertEqual(f2, update.form_id)
            self.assertEqual(f3, close.form_id)
        else:
            [create, u1, u2, u3, close] = case.actions
            self.assertEqual(f1, create.form_id)
            self.assertEqual(f1, u1.form_id)
            self.assertEqual(f2, u2.form_id)
            self.assertEqual(f3, u3.form_id)

        # todo: should this be the behavior for archiving the create form?
        form_acessors = FormAccessors(REBUILD_TEST_DOMAIN)
        f1_doc = form_acessors.get_form(f1)
        with capture_kafka_changes_context(topics.CASE_SQL) as change_context:
            f1_doc.archive()

        if should_use_sql_backend(case.domain):
            self.assertEqual([case.case_id], [change.id for change in change_context.changes])

        case = case_accessors.get_case(case_id)

        if should_use_sql_backend(REBUILD_TEST_DOMAIN):
            self.assertEqual(2, len(primary_actions(case)))
        else:
            self.assertEqual(3, len(primary_actions(case)))

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
            form_doc = form_acessors.get_form(form_id)
            form_doc.unarchive()
            case = case_accessors.get_case(case_id)
            _check_initial_state(case)

        _reset(f1)

        f2_doc = form_acessors.get_form(f2)
        f2_doc.archive()
        case = case_accessors.get_case(case_id)

        if should_use_sql_backend(REBUILD_TEST_DOMAIN):
            self.assertEqual(2, len(primary_actions(case)))
        else:
            self.assertEqual(4, len(primary_actions(case)))

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

        f3_doc = form_acessors.get_form(f3)
        f3_doc.archive()
        case = case_accessors.get_case(case_id)

        if should_use_sql_backend(REBUILD_TEST_DOMAIN):
            self.assertEqual(2, len(primary_actions(case)))
        else:
            self.assertEqual(3, len(primary_actions(case)))

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
        post_case_blocks(
            [create_block.as_xml()], form_extras={'received_on': way_earlier}
        )
        update_block = CaseBlock(case_id, update={'foo': 'bar'}, date_modified=earlier)
        post_case_blocks(
            [update_block.as_xml()], form_extras={'received_on': earlier}
        )

        case_accessors = CaseAccessors(REBUILD_TEST_DOMAIN)
        case = case_accessors.get_case(case_id)
        self.assertEqual(earlier, case.modified_on)

        second_form = FormAccessors(REBUILD_TEST_DOMAIN).get_form(case.xform_ids[-1])
        second_form.archive()
        case = case_accessors.get_case(case_id)
        self.assertEqual(way_earlier, case.modified_on)

    def test_archive_against_deleted_case(self):
        now = datetime.utcnow()
        # make sure we timestamp everything so they have the right order
        case_id = _post_util(create=True, p1='p1', form_extras={'received_on': now})
        _post_util(case_id=case_id, p2='p2',
                  form_extras={'received_on': now + timedelta(seconds=1)})
        _post_util(case_id=case_id, p3='p3',
                  form_extras={'received_on': now + timedelta(seconds=2)})

        case_accessors = CaseAccessors(REBUILD_TEST_DOMAIN)
        case = case_accessors.get_case(case_id)
        case_accessors.soft_delete_cases([case_id])

        [f1, f2, f3] = case.xform_ids
        f2_doc = FormAccessors(REBUILD_TEST_DOMAIN).get_form(f2)
        f2_doc.archive()
        case = case_accessors.get_case(case_id)
        self.assertTrue(case.is_deleted)

    def test_archive_removes_index(self):
        parent_case_id = uuid.uuid4().hex
        post_case_blocks([
            CaseBlock(parent_case_id, create=True).as_xml()
        ])
        child_case_id = uuid.uuid4().hex
        post_case_blocks([
            CaseBlock(child_case_id, create=True).as_xml()
        ])
        xform, _ = post_case_blocks([
            CaseBlock(child_case_id, index={'mom': ('mother', parent_case_id)}).as_xml()
        ])

        case_accessors = CaseAccessors(REBUILD_TEST_DOMAIN)
        case = case_accessors.get_case(child_case_id)
        self.assertEqual(1, len(case.indices))

        xform.archive()

        case = case_accessors.get_case(child_case_id)
        self.assertEqual(0, len(case.indices))


@use_sql_backend
class CaseRebuildTestSQL(CaseRebuildTest):
    pass


class TestCheckActionOrder(SimpleTestCase):

    def _action(self, datetime_):
        return CommCareCaseAction(server_date=datetime_, date=datetime_, action_type='update')

    def test_already_sorted(self):
        case = CommCareCase(actions=[
            self._action(datetime(2001, 1, 1, 0, 0, 0)),
            self._action(datetime(2001, 1, 2, 0, 0, 0)),
            self._action(datetime(2001, 1, 3, 0, 0, 0)),
        ])
        self.assertTrue(CouchCaseUpdateStrategy(case).check_action_order())

    def test_out_of_order(self):
        case = CommCareCase(actions=[
            self._action(datetime(2001, 1, 1, 0, 0, 0)),
            self._action(datetime(2001, 1, 3, 0, 0, 0)),
            self._action(datetime(2001, 1, 2, 0, 0, 0)),
        ])
        self.assertFalse(CouchCaseUpdateStrategy(case).check_action_order())


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

    def test_type_order_in_same_form(self):
        expected_actions = (
            (3, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_CLOSE, form_id='1')),
            (1, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_UPDATE, form_id='1')),
            (0, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_CREATE, form_id='1')),
            (2, _make_action(server_date=datetime(2001, 1, 1), action_type=const.CASE_ACTION_UPDATE, form_id='1')),
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


def _make_action(server_date, phone_date=EMPTY_DATE, action_type=const.CASE_ACTION_UPDATE, user_id='someuserid', form_id=None):
    if phone_date == EMPTY_DATE:
        phone_date = server_date
    form_id = form_id or uuid.uuid4().hex
    return CommCareCaseAction(
        action_type=action_type, server_date=server_date, date=phone_date, user_id=user_id, xform_id=form_id
    )
