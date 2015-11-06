from abc import ABCMeta, abstractproperty
import base64
import copy
from datetime import datetime
from functools import cmp_to_key
import logging
from PIL import Image
from StringIO import StringIO
from couchdbkit import BadValueError
import sys
from casexml.apps.case import const
from casexml.apps.case.exceptions import ReconciliationError, MissingServerDate, UsesReferrals
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.util import primary_actions
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from django.utils.translation import ugettext as _
from corehq.util.couch_helpers import CouchAttachmentsBuilder
from couchforms.models import XFormInstance
from couchforms.util import is_deprecation, is_override
from dimagi.utils import parsing
from dimagi.utils.logging import notify_exception
from dimagi.ext.couchdbkit import StringProperty


class UpdateStrategy(object):
    __metaclass__ = ABCMeta

    @abstractproperty
    def case_implementation_class(self):
        pass

    def __init__(self, case):
        self.case = case

    @classmethod
    def case_from_case_update(cls, case_update, xformdoc):
        """
        Create a case object from a case update object.
        """
        assert not is_deprecation(xformdoc)  # you should never be able to create a case from a deleted update
        case = cls.case_implementation_class()
        case.case_id = case_update.id

        if case_update.modified_on_str:
            case.modified_on = parsing.string_to_utc_datetime(case_update.modified_on_str)
        else:
            case.modified_on = datetime.utcnow()

        # apply initial updates, if present
        cls(case).update_from_case_update(case_update, xformdoc)
        return case

    @abstractproperty
    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        pass


class ActionsUpdateStrategy(UpdateStrategy):
    case_implementation_class = CommCareCase

    def check_action_order(self):
        action_dates = [a.server_date for a in self.case.actions if a.server_date]
        return action_dates == sorted(action_dates)

    def reconcile_actions_if_necessary(self, xform):
        if not self.check_action_order():
            try:
                self.reconcile_actions(rebuild=True, xforms={xform._id: xform})
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
                    error = u"Case {0} action server_date is None: {1}"
                elif a.xform_id is None:
                    error = u"Case {0} action xform_id is None: {1}"
                if error:
                    raise ReconciliationError(error.format(self.case.get_id, a))

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
                        error = (u"Case {0} action conflicts "
                                 u"with multiple other actions: {1}")
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
                error = u"Case {0} first action not create action: {1}"
                raise ReconciliationError(
                    error.format(self.case.get_id, sorted_actions[0])
                )
        self.case.actions = sorted_actions
        if rebuild:
            # it's pretty important not to block new case changes
            # just because previous case changes have been bad
            self.soft_rebuild_case(strict=False, xforms=xforms)

        return self

    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        if case_update.has_referrals():
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc._id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise UsesReferrals(_('Sorry, referrals are no longer supported!'))

        if is_deprecation(xformdoc):
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
        elif is_override(xformdoc):
            # This form is overriding a deprecated form.
            # Apply the actions just after the last action with this form type.
            # This puts the overriding actions in the right order relative to the others.
            prior_actions = [a for a in self.case.actions if a.xform_id == xformdoc._id]
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
        local_forms = {xformdoc._id: xformdoc}
        local_forms.update(other_forms or {})
        self.soft_rebuild_case(strict=False, xforms=local_forms)

        if case_update.version:
            self.case.version = case_update.version

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
                            'case_id': self.case._id,
                            'attribute': k,
                        }
                    )

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

    def soft_rebuild_case(self, strict=True, xforms=None):
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
            # only worry date reconciliation if in strict mode
            if strict:
                raise

        # remove all deprecated actions during rebuild.
        self.case.actions = [a for a in self.case.actions if not a.deprecated]
        actions = copy.deepcopy(list(self.case.actions))

        if strict:
            if actions[0].action_type != const.CASE_ACTION_CREATE:
                error = u"Case {0} first action not create action: {1}"
                raise ReconciliationError(
                    error.format(self.case.case_id, self.case.actions[0])
                )

        for a in actions:
            self._apply_action(a, xforms.get(a.xform_id))

        self.case.xform_ids = []
        for a in self.case.actions:
            if a.xform_id and a.xform_id not in self.case.xform_ids:
                self.case.xform_ids.append(a.xform_id)

        return self

    def _apply_action(self, action, xform):
        if action.action_type == const.CASE_ACTION_CREATE:
            self._apply_create_action(action)
        elif action.action_type == const.CASE_ACTION_UPDATE:
            self._apply_update_action(action)
        elif action.action_type == const.CASE_ACTION_INDEX:
            self.case.update_indices(action.indices)
        elif action.action_type == const.CASE_ACTION_CLOSE:
            self._apply_close_action(action)
        elif action.action_type == const.CASE_ACTION_ATTACHMENT:
            self._apply_attachments_action(action, xform)
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
            setattr(self.case, k, v)

        if not self.case.opened_on:
            self.case.opened_on = create_action.date
        if not self.case.opened_by:
            self.case.opened_by = create_action.user_id

    def _apply_update_action(self, update_action):
        """
        Applies updates to a case
        """
        for k, v in update_action.updated_known_properties.items():
            setattr(self.case, k, v)

        properties = self.case.properties()
        for item in update_action.updated_unknown_properties:
            if item not in const.CASE_TAGS:
                value = update_action.updated_unknown_properties[item]
                if isinstance(properties.get(item), StringProperty):
                    value = unicode(value)
                try:
                    self.case[item] = value
                except BadValueError:
                    notify_exception(None, "Can't set property {} on case {} from form {}".format(
                        item, self.case.case_id, update_action.xform_id
                    ))
                    raise

    def _apply_attachments_action(self, attachment_action, xform=None):
        """

        if xform is provided, attachments will be looked for
        in the xform's _attachments.
        They should be base64 encoded under _attachments[name]['data']

        """
        # the actions and _attachment must be added before the first saves can happen
        # todo attach cached attachment info
        def fetch_attachment(name):
            if xform and 'data' in xform._attachments[name]:
                assert xform._id == attachment_action.xform_id
                return base64.b64decode(xform._attachments[name]['data'])
            else:
                return XFormInstance.get_db().fetch_attachment(attachment_action.xform_id, name)

        stream_dict = {}
        # cache all attachment streams from xform
        for k, v in attachment_action.attachments.items():
            if v.is_present:
                # fetch attachment, update metadata, get the stream
                attach_data = fetch_attachment(v.attachment_src)
                stream_dict[k] = attach_data
                v.attachment_size = len(attach_data)

                if v.is_image:
                    img = Image.open(StringIO(attach_data))
                    img_size = img.size
                    props = dict(width=img_size[0], height=img_size[1])
                    v.attachment_properties = props

        update_attachments = {}
        for k, v in self.case.case_attachments.items():
            if v.is_present:
                update_attachments[k] = v

        if self.case._attachments:
            attachment_builder = CouchAttachmentsBuilder(
                self.case['_attachments'])
        else:
            attachment_builder = CouchAttachmentsBuilder()

        for k, v in attachment_action.attachments.items():
            # grab xform_attachments
            # copy over attachments from form onto case
            update_attachments[k] = v
            if v.is_present:
                #fetch attachment from xform
                attachment_key = v.attachment_key
                attach = stream_dict[attachment_key]
                attachment_builder.add(name=k, content=attach,
                                       content_type=v.server_mime)
            else:
                try:
                    attachment_builder.remove(k)
                except KeyError:
                    pass
                del update_attachments[k]
        self.case._attachments = attachment_builder.to_json()
        self.case.case_attachments = update_attachments

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

            def _sortkey(action):
                if not action.server_date or not action.date:
                    raise MissingServerDate()

                form_cmp = lambda form_id: (form_ids.index(form_id)
                                            if form_id in form_ids else sys.maxint, form_id)
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
