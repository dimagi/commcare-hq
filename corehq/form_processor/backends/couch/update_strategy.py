from __future__ import absolute_import
from __future__ import unicode_literals
import copy
from functools import cmp_to_key
import logging
from PIL import Image
from io import BytesIO
from couchdbkit import BadValueError
import sys
from datetime import date, datetime
from casexml.apps.case import const
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import ReconciliationError, MissingServerDate, UsesReferrals
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import primary_actions
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from django.utils.translation import ugettext as _
from corehq.form_processor.update_strategy_base import UpdateStrategy
from couchforms.models import XFormInstance
from dimagi.utils.logging import notify_exception
from dimagi.ext.couchdbkit import StringProperty
import six


def coerce_to_datetime(v):
    if isinstance(v, date) and not isinstance(v, datetime):
        return datetime.combine(v, datetime.min.time())
    else:
        return v


PROPERTY_TYPE_MAPPING = {
    'opened_on': coerce_to_datetime
}


def _convert_type(property_name, value):
    return PROPERTY_TYPE_MAPPING.get(property_name, lambda x: x)(value)


def _is_override(xform):
    # it's an override if we've explicitly set the "deprecated_form_id" property on it.
    return bool(getattr(xform, 'deprecated_form_id', None))


class CouchCaseUpdateStrategy(UpdateStrategy):
    case_implementation_class = CommCareCase

    def apply_action_intents(self, primary_intent, deprecation_intent=None):
        case = self.case
        if deprecation_intent:
            # just remove the old stock actions for the form from the case
            case.actions = [
                a for a in case.actions if not
                (a.xform_id == deprecation_intent.form_id and a.action_type == CASE_ACTION_COMMTRACK)
            ]

        # for now we only allow commtrack actions to be processed this way so just assert that's the case
        assert primary_intent.action_type == CASE_ACTION_COMMTRACK
        case_action = primary_intent.get_couch_action()
        # hack: clear the sync log id so this modification always counts
        # since consumption data could change server-side
        case_action.sync_log_id = ''
        case.actions.append(case_action)
        if primary_intent.form_id not in case.xform_ids:
            case.xform_ids.append(primary_intent.form_id)

    def check_action_order(self):
        action_dates = [a.server_date for a in self.case.actions if a.server_date]
        return action_dates == sorted(action_dates)

    def reconcile_actions_if_necessary(self, xform):
        if not self.check_action_order():
            try:
                self.reconcile_actions(rebuild=True, xforms={xform.form_id: xform})
            except ReconciliationError:
                pass

    def reconcile_actions(self, rebuild=False, xforms=None):
        """
        Runs through the action list and tries to reconcile things that seem
        off (for example, out-of-order submissions, duplicate actions, etc.).

        This method raises a ReconciliationError if anything goes wrong.
        """
        def _check_preconditions():
            error = None
            for a in self.case.actions:
                if a.server_date is None:
                    error = "Case {0} action server_date is None: {1}"
                elif a.xform_id is None:
                    error = "Case {0} action xform_id is None: {1}"
                if error:
                    raise ReconciliationError(error.format(self.case.case_id, a))

        _check_preconditions()

        # this would normally work except we only recently started using the
        # form timestamp as the modification date so we have to do something
        # fancier to deal with old data
        deduplicated_actions = list(set(self.case.actions))

        def _further_deduplicate(action_list):
            def actions_match(a1, a2):
                # if everything but the server_date match, the actions match.
                # this will allow for multiple case blocks to be submitted
                # against the same case in the same form so long as they
                # are different
                a1doc = copy.copy(a1._doc)
                a2doc = copy.copy(a2._doc)
                a2doc['server_date'] = a1doc['server_date']
                a2doc['date'] = a1doc['date']
                return a1doc == a2doc

            ret = []
            for a in action_list:
                found_actions = [other for other in ret if actions_match(a, other)]
                if found_actions:
                    if len(found_actions) != 1:
                        error = ("Case {0} action conflicts "
                                 "with multiple other actions: {1}")
                        raise ReconciliationError(error.format(self.case.case_id, a))
                    match = found_actions[0]
                    # when they disagree, choose the _earlier_ one as this is
                    # the one that is likely timestamped with the form's date
                    # (and therefore being processed later in absolute time)
                    ret[ret.index(match)] = a if a.server_date < match.server_date else match
                else:
                    ret.append(a)
            return ret

        deduplicated_actions = _further_deduplicate(deduplicated_actions)
        sorted_actions = sorted(
            deduplicated_actions,
            key=_action_sort_key_function(self.case)
        )
        if sorted_actions:
            if sorted_actions[0].action_type != const.CASE_ACTION_CREATE:
                error = "Case {0} first action not create action: {1}"
                raise ReconciliationError(
                    error.format(self.case.case_id, sorted_actions[0])
                )
        self.case.actions = sorted_actions
        if rebuild:
            # it's pretty important not to block new case changes
            # just because previous case changes have been bad
            self.soft_rebuild_case(xforms=xforms)

        return self

    def update_from_case_update(self, case_update, xformdoc):
        if case_update.has_referrals():
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc.form_id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise UsesReferrals(_('Sorry, referrals are no longer supported!'))

        if xformdoc.is_deprecated:
            # Mark all of the form actions as deprecated. These will get removed on rebuild.
            # This assumes that there is a second update coming that will actually
            # reapply the equivalent actions from the form that caused the current
            # one to be deprecated (which is what happens in form processing).
            for a in self.case.actions:
                if a.xform_id == xformdoc.orig_id:
                    a.deprecated = True

            # short circuit the rest of this since we don't actually want to
            # do any case processing
            return
        elif _is_override(xformdoc):
            # This form is overriding a deprecated form.
            # Apply the actions just after the last action with this form type.
            # This puts the overriding actions in the right order relative to the others.
            prior_actions = [a for a in self.case.actions if a.xform_id == xformdoc.form_id]
            if prior_actions:
                action_insert_pos = self.case.actions.index(prior_actions[-1]) + 1
                # slice insertion
                # http://stackoverflow.com/questions/7376019/python-list-extend-to-index/7376026#7376026
                self.case.actions[action_insert_pos:action_insert_pos] = case_update.get_case_actions(xformdoc)
            else:
                self.case.actions.extend(case_update.get_case_actions(xformdoc))
        else:
            # normal form - just get actions and apply them on the end
            self.case.actions.extend(case_update.get_case_actions(xformdoc))

        # rebuild the case
        self.soft_rebuild_case()

        if case_update.version:
            self.case.version = case_update.version

        if self.case.domain:
            assert hasattr(self.case, 'type')
            self.case['#export_tag'] = ["domain", "type"]

    def reset_case_state(self):
        """
        Clear known case properties, and all dynamic properties
        """
        dynamic_properties = set([
            k for action in self.case.actions
            for k in action.updated_unknown_properties.keys()
        ])
        for k in dynamic_properties:
            try:
                delattr(self.case, k)
            except KeyError:
                pass
            except AttributeError:
                # 'case_id' is not a valid property so don't worry about spamming
                # this error.
                if k != 'case_id':
                    logging.error(
                        "Cannot delete attribute '%(attribute)s' from case '%(case_id)s'" % {
                            'case_id': self.case.case_id,
                            'attribute': k,
                        }
                    )

        self.case.indices = []

        # already deleted means it was explicitly set to "deleted",
        # as opposed to getting set to that because it has no actions
        already_deleted = self.case.doc_type == 'CommCareCase-Deleted' and primary_actions(self.case)
        if not already_deleted:
            self.case.doc_type = 'CommCareCase'

        # hard-coded normal properties (from a create block)
        for prop, default_value in KNOWN_PROPERTIES.items():
            setattr(self.case, prop, default_value)

        self.case.closed = False
        self.case.modified_on = None
        self.case.closed_on = None
        self.case.closed_by = ''
        return self

    def soft_rebuild_case(self, xforms=None):
        """
        Rebuilds the case state in place from its actions.

        If strict is True, this will enforce that the first action must be a create.
        """
        xforms = xforms or {}
        self.reset_case_state()
        # try to re-sort actions if necessary
        try:
            self.case.actions = sorted(self.case.actions, key=_action_sort_key_function(self.case))
        except MissingServerDate:
            pass

        # remove all deprecated actions during rebuild.
        self.case.actions = [a for a in self.case.actions if not a.deprecated]
        actions = copy.deepcopy(list(self.case.actions))

        for a in actions:
            self._apply_action(a, xforms.get(a.xform_id))

        self.case.xform_ids = []
        for a in self.case.actions:
            if a.xform_id and a.xform_id not in self.case.xform_ids:
                self.case.xform_ids.append(a.xform_id)

        return self

    def _apply_action(self, action):
        if action.action_type == const.CASE_ACTION_CREATE:
            self._apply_create_action(action)
        elif action.action_type == const.CASE_ACTION_UPDATE:
            self._apply_update_action(action)
        elif action.action_type == const.CASE_ACTION_INDEX:
            self.case.update_indices(action.indices)
        elif action.action_type == const.CASE_ACTION_CLOSE:
            self._apply_close_action(action)
        elif action.action_type in (const.CASE_ACTION_COMMTRACK, const.CASE_ACTION_REBUILD):
            return  # no action needed here, it's just a placeholder stub
        else:
            raise ValueError("Can't apply action of type %s: %s" % (
                action.action_type,
                self.case.case_id,
            ))

        # override any explicit properties from the update
        if action.user_id:
            self.case.user_id = action.user_id
        if self.case.modified_on is None or action.date > self.case.modified_on:
            self.case.modified_on = action.date

    def _apply_create_action(self, create_action):
        """
        Applies a create block to a case.

        Note that all unexpected attributes are ignored (thrown away)
        """
        for k, v in create_action.updated_known_properties.items():
            setattr(self.case, k, _convert_type(k, v))

        if not self.case.opened_on:
            self.case.opened_on = create_action.date
        if not self.case.opened_by:
            self.case.opened_by = create_action.user_id

    def _apply_update_action(self, update_action):
        """
        Applies updates to a case
        """
        for k, v in update_action.updated_known_properties.items():
            setattr(self.case, k, _convert_type(k, v))

        properties = self.case.properties()
        for item in update_action.updated_unknown_properties:
            if item not in const.RESTRICTED_PROPERTIES:
                value = update_action.updated_unknown_properties[item]
                if isinstance(properties.get(item), StringProperty):
                    value = six.text_type(value)
                try:
                    self.case[item] = value
                except (AttributeError, BadValueError):
                    notify_exception(None, "Can't set property {} on case {} from form {}".format(
                        item, self.case.case_id, update_action.xform_id
                    ))
                    raise

    def _apply_close_action(self, close_action):
        self.case.closed = True
        self.case.closed_on = close_action.date
        self.case.closed_by = close_action.user_id


def _action_sort_key_function(case):
    def _action_cmp(first_action, second_action):
        # if the forms aren't submitted by the same user, just default to server dates
        if first_action.user_id != second_action.user_id:
            return cmp(first_action.server_date, second_action.server_date)
        else:
            form_ids = list(case.xform_ids)

            if first_action.xform_id and first_action.xform_id == second_action.xform_id:
                # short circuit if they are from the same form
                return cmp(
                    _type_sort(first_action.action_type),
                    _type_sort(second_action.action_type)
                )

            def _sortkey(action):
                if not action.server_date or not action.date:
                    raise MissingServerDate()

                def form_cmp(form_id):
                    return form_ids.index(form_id) if form_id in form_ids else sys.maxsize

                # if the user is the same you should compare with the special logic below
                # if the user is not the same you should compare just using received_on
                return (
                    # this is sneaky - it's designed to use just the date for the
                    # server time in case the phone submits two forms quickly out of order
                    action.server_date.date(),
                    action.date,
                    form_cmp(action.xform_id),
                    _type_sort(action.action_type),
                )

            return cmp(_sortkey(first_action), _sortkey(second_action))

    return cmp_to_key(_action_cmp)


def _type_sort(action_type):
    """
    Consistent ordering for action types
    """
    return const.CASE_ACTIONS.index(action_type)
