import logging
from collections import defaultdict

from iso8601 import iso8601

from casexml.apps.case import const
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import UsesReferrals, VersionNotSupported, CaseValueError
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml import V2
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES
from corehq.apps.couch_sql_migration.progress import couch_sql_migration_in_progress
from corehq.form_processor.models import CommCareCaseSQL, CommCareCaseIndexSQL, CaseTransaction, CaseAttachmentSQL
from corehq.form_processor.update_strategy_base import UpdateStrategy
from django.utils.translation import ugettext as _

from corehq.util.soft_assert import soft_assert


def _validate_length(length):
    def __inner(value):
        if len(value) > length:
            raise ValueError('Value exceeds allowed length: {}'.format(length))

        return value

    return __inner


PROPERTY_TYPE_MAPPING = {
    'opened_on': iso8601.parse_date,
    'name': _validate_length(255),
    'type': _validate_length(255),
    'owner_id': _validate_length(255),
    'external_id': _validate_length(255),
}


def _convert_type_check_length(property_name, value):
    try:
        return PROPERTY_TYPE_MAPPING.get(property_name, lambda x: x)(value)
    except ValueError as e:
        raise CaseValueError('Error processing case update: Field: {}, Error: {}'.format(property_name, str(e)))


class SqlCaseUpdateStrategy(UpdateStrategy):
    case_implementation_class = CommCareCaseSQL

    def apply_action_intents(self, primary_intent, deprecation_intent=None):
        # for now we only allow commtrack actions to be processed this way so just assert that's the case
        if primary_intent:
            assert primary_intent.action_type == CASE_ACTION_COMMTRACK
            transaction = CaseTransaction.ledger_transaction(self.case, primary_intent.form)
            if deprecation_intent:
                assert transaction.is_saved()
            elif transaction not in self.case.get_tracked_models_to_create(CaseTransaction):
                # hack: clear the sync log id so this modification always counts
                # since consumption data could change server-side
                transaction.sync_log_id = None
                self.case.track_create(transaction)
        elif deprecation_intent:
            transaction = self.case.get_transaction_by_form_id(deprecation_intent.form.orig_id)
            transaction.sync_log_id = None
            transaction.type -= CaseTransaction.TYPE_LEDGER
            self.case.track_update(transaction)

    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        self._apply_case_update(case_update, xformdoc)

        types = [CaseTransaction.type_from_action_type_slug(a.action_type_slug) for a in case_update.actions]
        transaction = CaseTransaction.form_transaction(self.case, xformdoc, types)
        if transaction not in self.case.get_tracked_models_to_create(CaseTransaction):
            # don't add multiple transactions for the same form
            self.case.track_create(transaction)

    def _apply_case_update(self, case_update, xformdoc):
        sql_migration_in_progress = couch_sql_migration_in_progress(xformdoc.domain)
        if case_update.has_referrals() and not sql_migration_in_progress:
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc.form_id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise UsesReferrals(_('Sorry, referrals are no longer supported!'))

        if case_update.version and case_update.version != V2 and not sql_migration_in_progress:
            raise VersionNotSupported

        if not case_update.user_id and xformdoc.user_id:
            # hack for migration from V1 case blocks
            case_update.user_id = xformdoc.user_id

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

        # edge case if form updates case before it's been created (or creation form archived)
        if not self.case.opened_on:
            self.case.opened_on = modified_on
        if not self.case.opened_by:
            self.case.opened_by = case_update.user_id
        if not self.case.owner_id:
            self.case.owner_id = case_update.user_id

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
                setattr(self.case, name, _convert_type_check_length(name, value))

    def _apply_create_action(self, case_update, create_action):
        self._update_known_properties(create_action)

    def _apply_update_action(self, update_action):
        self._update_known_properties(update_action)

        for key, value in update_action.dynamic_properties.items():
            if key == 'location_id':
                # special treatment of location_id
                self.case.location_id = value
            elif key == 'name':
                # replicate legacy behaviour
                self.case.name = value
            elif key not in const.RESTRICTED_PROPERTIES:
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
                        domain=self.case.domain,
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
                if identifier in current_attachments:
                    existing_attachment = current_attachments[identifier]
                    existing_attachment.from_form_attachment(form_attachment)
                    self.case.track_update(existing_attachment)
                else:
                    new_attachment.from_form_attachment(form_attachment)
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
        """
        self.case.case_json = {}
        self.case.deleted = False

        # hard-coded normal properties (from a create block)
        for prop, default_value in KNOWN_PROPERTIES.items():
            setattr(self.case, prop, default_value)

        self.case.opened_on = None
        self.case.opened_by = ''
        self.case.modified_on = None
        self.case.modified_by = ''
        self.case.closed = False
        self.case.closed_on = None
        self.case.closed_by = ''
        self._deduplicate_indices()

    def _deduplicate_indices(self):
        # http://manage.dimagi.com/default.asp?261458
        # Can be removed once we have a unique index on case indices
        indices_by_id = defaultdict(list)
        for index in self.case.indices:
            indices_by_id[index.identifier].append(index)

        for identifier, indices in indices_by_id.items():
            if len(indices) > 1:
                index_set = set(indices)
                if len(index_set) == 1:
                    for index_to_delete in indices[1:]:
                        # delete all except the first
                        self.case.track_delete(index_to_delete)
                    self.case._saved_indices.reset_cache(self.case)
                else:
                    soft_assert('{}@dimagi.com'.format('skelly'))(
                        False,
                        "Multiple case indices with same identifier",
                        {
                            'case_id': self.case.case_id,
                            'indices': [unicode(index) for index in index_set]
                        }
                    )

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

        original_indices = {index.identifier: index for index in self.case.indices}
        original_attachments = {attach.identifier: attach for attach in self.case.get_attachments()}

        real_transactions = []
        for transaction in transactions:
            if transaction.is_form_transaction and transaction.is_relevant:
                self._apply_form_transaction(transaction)
                real_transactions.append(transaction)

        self._delete_old_related_models(original_indices, self.case.get_live_tracked_models(CommCareCaseIndexSQL))
        self._delete_old_related_models(original_attachments, self.case.get_live_tracked_models(CaseAttachmentSQL))

        self.case.deleted = already_deleted or not bool(real_transactions)

        self.case.track_create(rebuild_transaction)
        if not self.case.modified_on:
            self.case.modified_on = rebuild_transaction.server_date

    def _delete_old_related_models(self, original_models_by_id, models_to_keep):
        for model in models_to_keep:
            original_models_by_id.pop(model.identifier, None)

        for model in original_models_by_id.values():
            self.case.track_delete(model)

    def _apply_form_transaction(self, transaction):
        form = transaction.form
        if form:
            assert form.domain == self.case.domain
            case_updates = get_case_updates(form)
            filtered_updates = [u for u in case_updates if u.id == self.case.case_id]
            for case_update in filtered_updates:
                self._apply_case_update(case_update, form)
