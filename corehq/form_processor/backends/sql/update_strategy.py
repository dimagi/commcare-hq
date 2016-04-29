import logging

from iso8601 import iso8601

from casexml.apps.case import const
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import UsesReferrals, VersionNotSupported
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml import V2
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from corehq.form_processor.models import CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction, CaseAttachmentSQL
from corehq.form_processor.update_strategy_base import UpdateStrategy
from django.utils.translation import ugettext as _

PROPERTY_TYPE_MAPPING = {
    'opened_on': iso8601.parse_date
}


def _convert_type(property_name, value):
    return PROPERTY_TYPE_MAPPING.get(property_name, lambda x: x)(value)


class SqlCaseUpdateStrategy(UpdateStrategy):
    case_implementation_class = CommCareCaseSQL

    def apply_action_intents(self, primary_intent, deprecation_intent=None):
        # for now we only allow commtrack actions to be processed this way so just assert that's the case
        assert primary_intent.action_type == CASE_ACTION_COMMTRACK
        transaction = CaseTransaction.ledger_transaction(self.case, primary_intent.form)
        if deprecation_intent:
            assert transaction.is_saved()
        elif transaction not in self.case.get_tracked_models_to_create(CaseTransaction):
            self.case.track_create(transaction)

        # TODO: do we need to support unsetting the ledger flag on a transaction
        # if the form previously had ledgers but now does not

    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        self._apply_case_update(case_update, xformdoc)

        types = [CaseTransaction.type_from_action_type_slug(a.action_type_slug) for a in case_update.actions]
        transaction = CaseTransaction.form_transaction(self.case, xformdoc, types)
        if transaction not in self.case.get_tracked_models_to_create(CaseTransaction):
            # don't add multiple transactions for the same form
            self.case.track_create(transaction)

    def _apply_case_update(self, case_update, xformdoc):
        if case_update.has_referrals():
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc.form_id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise UsesReferrals(_('Sorry, referrals are no longer supported!'))

        if case_update.version and case_update.version != V2:
            raise VersionNotSupported

        if xformdoc.is_deprecated:
            return

        for action in case_update.actions:
            self._apply_action(case_update, action, xformdoc)

        # override any explicit properties from the update
        if case_update.user_id:
            self.case.modified_by = case_update.user_id

        modified_on = case_update.guess_modified_on()
        if self.case.modified_on is None or modified_on > self.case.modified_on:
            self.case.modified_on = modified_on

    def _apply_action(self, case_update, action, xform):
        if action.action_type_slug == const.CASE_ACTION_CREATE:
            self._apply_create_action(case_update, action)
        elif action.action_type_slug == const.CASE_ACTION_UPDATE:
            self._apply_update_action(action)
        elif action.action_type_slug == const.CASE_ACTION_INDEX:
            self._apply_index_action(action)
        elif action.action_type_slug == const.CASE_ACTION_CLOSE:
            self._apply_close_action(case_update)
        elif action.action_type_slug == const.CASE_ACTION_ATTACHMENT:
            self._apply_attachments_action(action, xform)
        else:
            raise ValueError("Can't apply action of type %s: %s" % (
                action.action_type,
                self.case.case_id,
            ))

    def _update_known_properties(self, action):
        for name, value in action.get_known_properties().items():
            if value:
                setattr(self.case, name, _convert_type(name, value))

    def _apply_create_action(self, case_update, create_action):
        self._update_known_properties(create_action)

        if not self.case.opened_on:
            self.case.opened_on = case_update.guess_modified_on()
        if not self.case.opened_by:
            self.case.opened_by = case_update.user_id
        if not self.case.owner_id:
            self.case.owner_id = case_update.user_id

    def _apply_update_action(self, update_action):
        self._update_known_properties(update_action)

        for key, value in update_action.dynamic_properties.items():
            if key == 'location_id':
                # special treatment of location_id
                self.case.location_id = value
            elif key not in const.CASE_TAGS:
                self.case.case_json[key] = value

            if key == 'hq_user_id':
                # also save hq_user_id to external_id
                self.case.external_id = value

    def _apply_index_action(self, action):
        if not action.indices:
            return

        for index_update in action.indices:
            if self.case.has_index(index_update.identifier):
                if not index_update.referenced_id:
                    # empty ID = delete
                    index = self.case.get_index(index_update.identifier)
                    self.case.track_delete(index)
                else:
                    # update
                    index = self.case.get_index(index_update.identifier)
                    index.referenced_type = index_update.referenced_type
                    index.referenced_id = index_update.referenced_id
                    index.relationship = index_update.relationship
                    self.case.track_update(index)
            else:
                # no id, no index
                if index_update.referenced_id:
                    index = CommCareCaseIndexSQL(
                        case=self.case,
                        identifier=index_update.identifier,
                        referenced_type=index_update.referenced_type,
                        referenced_id=index_update.referenced_id,
                        relationship=index_update.relationship
                    )
                    self.case.track_create(index)

    def _apply_attachments_action(self, attachment_action, xform):
        current_attachments = self.case.case_attachments
        for identifier, att in attachment_action.attachments.items():
            new_attachment = CaseAttachmentSQL.from_case_update(att)
            if new_attachment.is_present:
                form_attachment = xform.get_attachment_meta(att.attachment_src)
                new_attachment.update_from_attachment(form_attachment)

                if identifier in current_attachments:
                    existing_attachment = current_attachments[identifier]
                    existing_attachment.update_from_attachment(new_attachment)
                    existing_attachment.copy_content(form_attachment)
                    self.case.track_update(existing_attachment)
                else:
                    new_attachment.copy_content(form_attachment)
                    new_attachment.case = self.case
                    self.case.track_create(new_attachment)
            elif identifier in current_attachments:
                existing_attachment = current_attachments[identifier]
                self.case.track_delete(existing_attachment)

    def _apply_close_action(self, case_update):
        self.case.closed = True
        self.case.closed_on = case_update.guess_modified_on()
        self.case.closed_by = case_update.user_id

    def _reset_case_state(self):
        """
        Clear known case properties, and all dynamic properties
        Note: does not alter case indices or attachments. For indices this isn't an issue
        since we only allow creating indices at case creation (via the app builder) and also
        don't support optionally creating indices.
        """
        self.case.case_json = {}
        self.case.deleted = False

        # hard-coded normal properties (from a create block)
        for prop, default_value in KNOWN_PROPERTIES.items():
            setattr(self.case, prop, default_value)

        self.case.closed = False
        self.case.modified_on = None
        self.case.closed_on = None
        self.case.closed_by = ''
        self.case.opened_by = None

    def rebuild_from_transactions(self, transactions, rebuild_transaction, unarchived_form_id=None):
        """
        :param transactions:        The transactions required to rebuild the case
        :param rebuild_transaction: The transaction to add for this rebuild
        :param unarchived_form_id:  If this rebuild was triggered by a form being unarchived then this is
                                    its ID.
        """
        already_deleted = False
        if self.case.is_deleted:
            # we exclude the transaction of the form being unarchived since it would
            # have been revoked prior to the rebuild.
            primary_transactions = [
                tx for tx in transactions
                if not tx.is_case_rebuild and tx.form_id != unarchived_form_id
            ]
            if primary_transactions:
                # already deleted means it was explicitly set to "deleted",
                # as opposed to getting set to that because it has no 'real' transactions
                already_deleted = True

        self._reset_case_state()

        real_transactions = []
        for transaction in transactions:
            if not transaction.is_relevant:
                continue
            elif transaction.is_form_transaction:
                self._apply_form_transaction(transaction)
                real_transactions.append(transaction)

        self.case.deleted = already_deleted or not bool(real_transactions)

        self.case.track_create(rebuild_transaction)
        if not self.case.modified_on:
            self.case.modified_on = rebuild_transaction.server_date

    def _apply_form_transaction(self, transaction):
        form = transaction.form
        if form:
            assert form.domain == self.case.domain
            case_updates = get_case_updates(form)
            filtered_updates = [u for u in case_updates if u.id == self.case.case_id]
            # TODO: stock
            # stock_actions = get_stock_actions(form)
            # case_actions.extend([intent.action
            #                      for intent in stock_actions.case_action_intents
            #                      if not intent.is_deprecation])
            for case_update in filtered_updates:
                self._apply_case_update(case_update, form)
