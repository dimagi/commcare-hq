import logging
import sys
from functools import cmp_to_key

from django.utils.translation import gettext as _

from ddtrace import tracer
from iso8601 import iso8601

from casexml.apps.case import const
from casexml.apps.case.const import CASE_ACTION_COMMTRACK
from casexml.apps.case.exceptions import (
    CaseValueError,
    MissingServerDate,
    ReconciliationError,
    UsesReferrals,
    VersionNotSupported,
)
from casexml.apps.case.xform import get_case_updates
from casexml.apps.case.xml import V2
from casexml.apps.case.xml.parser import KNOWN_PROPERTIES

from corehq import toggles
from corehq.form_processor.exceptions import StockProcessingError
from corehq.form_processor.models import (
    CaseAttachment,
    CaseTransaction,
    CommCareCaseIndex,
    CommCareCase,
    RebuildWithReason,
    STANDARD_CHARFIELD_LENGTH,
)
from corehq.form_processor.models.forms import XFormInstance, XFormNotFound
from corehq.form_processor.update_strategy_base import UpdateStrategy
from corehq.util import cmp
from corehq.util.metrics import metrics_counter
from corehq.util.metrics.load_counters import form_load_counter
from corehq.util.soft_assert import soft_assert

reconciliation_soft_assert = soft_assert('@'.join(['dmiller', 'dimagi.com']))


def _validate_length(length):
    def __inner(value):
        if len(value) > length:
            raise ValueError('Value exceeds allowed length: {}'.format(length))

        return value

    return __inner


PROPERTY_TYPE_MAPPING = {
    'opened_on': iso8601.parse_date,
    'name': _validate_length(STANDARD_CHARFIELD_LENGTH),
    'type': _validate_length(STANDARD_CHARFIELD_LENGTH),
    'owner_id': _validate_length(STANDARD_CHARFIELD_LENGTH),
    'external_id': _validate_length(STANDARD_CHARFIELD_LENGTH),
}


def _convert_type_check_length(property_name, value):
    try:
        return PROPERTY_TYPE_MAPPING.get(property_name, lambda x: x)(value)
    except ValueError as e:
        raise CaseValueError('Error processing case update: Field: {}, Error: {}'.format(property_name, str(e)))


class SqlCaseUpdateStrategy(UpdateStrategy):
    case_implementation_class = CommCareCase

    def apply_action_intents(self, primary_intent, deprecation_intent=None):
        # for now we only allow commtrack actions to be processed this way so just assert that's the case

        if primary_intent:
            if primary_intent.action_type != CASE_ACTION_COMMTRACK:
                raise StockProcessingError('intent not of expected type: {}'.format(primary_intent.action_type))
            if not deprecation_intent:
                # don't create / update transaction if we're processing an edited form
                transaction = CaseTransaction.ledger_transaction(self.case, primary_intent.form)
                if transaction not in self.case.get_tracked_models_to_create(CaseTransaction):
                    # hack: clear the sync log id so this modification always counts
                    # since consumption data could change server-side
                    transaction.sync_log_id = None
                    self.case.track_create(transaction)
        elif deprecation_intent:
            # edited form no longer has a ledger block to update existing transaction
            # to remove leger type
            transaction = self.case.get_transaction_by_form_id(deprecation_intent.form.orig_id)
            if not transaction.is_saved():
                raise StockProcessingError('Deprecated transaction not saved')
            transaction.sync_log_id = None
            transaction.type -= CaseTransaction.TYPE_LEDGER
            self.case.track_update(transaction)

    def update_from_case_update(self, case_update, xformdoc, other_forms=None):
        self._apply_case_update(case_update, xformdoc)
        self.add_transaction_for_form(self.case, case_update, xformdoc)

    @staticmethod
    def add_transaction_for_form(case, case_update, form):
        types = [CaseTransaction.type_from_action_type_slug(a.action_type_slug) for a in case_update.actions]
        transaction = CaseTransaction.form_transaction(case, form, case_update.guess_modified_on(), types)
        if transaction not in case.get_tracked_models_to_create(CaseTransaction):
            case.track_create(transaction)

    def _apply_case_update(self, case_update, xformdoc):
        if case_update.has_referrals():
            logging.error('Form {} touching case {} in domain {} is still using referrals'.format(
                xformdoc.form_id, case_update.id, getattr(xformdoc, 'domain', None))
            )
            raise UsesReferrals(_('Sorry, referrals are no longer supported!'))

        if case_update.version and case_update.version != V2:
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
            if value is not None:
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
                self.case.name = _convert_type_check_length(key, value)
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
                # update
                index = self.case.get_index(index_update.identifier)
                index.referenced_type = index_update.referenced_type
                index.referenced_id = index_update.referenced_id
                index.relationship = index_update.relationship
                self.case.track_update(index)
            else:
                # no id, no index
                if index_update.referenced_id:
                    index = CommCareCaseIndex(
                        domain=self.case.domain,
                        case=self.case,
                        identifier=index_update.identifier,
                        referenced_type=index_update.referenced_type,
                        referenced_id=index_update.referenced_id,
                        relationship=index_update.relationship
                    )
                    self.case.track_create(index)

    def _apply_attachments_action(self, attachment_action, xform):
        if not toggles.MM_CASE_PROPERTIES.enabled(self.case.domain):
            return

        # NOTE `attachment_action` is a
        # `casexml.apps.case.xml.parser.CaseAttachmentAction` and
        # `attachment_action.attachments` is a dict with values of
        # `casexml.apps.case.xml.parser.CaseAttachment`

        current_attachments = self.case.case_attachments
        for name, att in attachment_action.attachments.items():
            if att.is_delete:
                if name in current_attachments:
                    self.case.track_delete(current_attachments[name])
            elif att.attachment_src:
                form_attachment = xform.get_attachment_meta(att.attachment_src)
                if name in current_attachments:
                    existing_attachment = current_attachments[name]
                    existing_attachment.from_form_attachment(
                        form_attachment, att.attachment_src)
                    self.case.track_update(existing_attachment)
                else:
                    new_attachment = CaseAttachment.new(att.identifier)
                    new_attachment.from_form_attachment(
                        form_attachment, att.attachment_src)
                    new_attachment.case = self.case
                    self.case.track_create(new_attachment)

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
        original_attachments = {attach.name: attach for attach in self.case.get_attachments()}

        real_transactions = []
        for transaction in transactions:
            if transaction.is_form_transaction and transaction.is_relevant:
                self._apply_form_transaction(transaction)
                real_transactions.append(transaction)
                if not transaction.is_saved():
                    self.case.track_create(transaction)

        self._delete_old_related_models(
            original_indices,
            self.case.get_live_tracked_models(CommCareCaseIndex)
        )
        self._delete_old_related_models(
            original_attachments,
            self.case.get_live_tracked_models(CaseAttachment),
            key="name",
        )

        self.case.deleted = already_deleted or not bool(real_transactions)

        self.case.track_create(rebuild_transaction)
        if not self.case.modified_on:
            self.case.modified_on = rebuild_transaction.server_date

    def reconcile_transactions_if_necessary(self):
        if self.case.check_transaction_order():
            return False
        metrics_counter("commcare.form_processor.sql.reconcile_transactions")
        try:
            self.reconcile_transactions()
        except ReconciliationError as e:
            reconciliation_soft_assert(False, "ReconciliationError: %s" % str(e))

        return True

    @tracer.wrap(name='form_processor.sql.reconcile_transactions')
    def reconcile_transactions(self):
        transactions = self.case.transactions
        sorted_transactions = sorted(
            transactions,
            key=_transaction_sort_key_function(self.case)
        )
        if sorted_transactions:
            if not sorted_transactions[0].is_case_create:
                error = "Case {0} first transaction not create transaction: {1}"
                raise ReconciliationError(
                    error.format(self.case.case_id, sorted_transactions[0])
                )

        self._fetch_case_transaction_forms(sorted_transactions)
        rebuild_detail = RebuildWithReason(reason="client_date_reconciliation")
        rebuild_transaction = CaseTransaction.rebuild_transaction(self.case, rebuild_detail)
        self.rebuild_from_transactions(sorted_transactions, rebuild_transaction)

    def _delete_old_related_models(self, original_models_by_id, models_to_keep, key="identifier"):
        for model in models_to_keep:
            original_models_by_id.pop(getattr(model, key), None)

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

    def get_transactions_for_rebuild(self, updated_xforms=None):
        """
        Fetch all the transactions required to rebuild the case along
        with all the forms for those transactions.

        For any forms that have been updated it replaces the old form
        with the new one.

        :param updated_xforms: optional list of forms that have been changed.
        :return: list of ``CaseTransaction`` objects with their associated forms attached.
        """
        transactions = CaseTransaction.objects.get_transactions_for_case_rebuild(self.case.case_id)
        self._fetch_case_transaction_forms(transactions, updated_xforms)
        return transactions

    def _fetch_case_transaction_forms(self, transactions, updated_xforms=None):
        """
        Fetch the forms for a list of transactions, caching them on each transaction

        :param transactions: list of ``CaseTransaction`` objects:
        :param updated_xforms: optional list of forms that have been changed.
        """
        form_ids = {tx.form_id for tx in transactions if tx.form_id}
        updated_xforms_map = {
            xform.form_id: xform for xform in updated_xforms if not xform.is_deprecated
        } if updated_xforms else {}

        updated_xform_ids = set(updated_xforms_map)
        form_ids_to_fetch = list(form_ids - updated_xform_ids)
        form_load_counter("rebuild_case", self.case.domain)(len(form_ids_to_fetch))
        xform_map = {
            form.form_id: form
            for form in XFormInstance.objects.get_forms_with_attachments_meta(form_ids_to_fetch)
        }

        forms_missing_transactions = list(updated_xform_ids - form_ids)
        for form_id in forms_missing_transactions:
            # Add in any transactions that aren't already present
            form = updated_xforms_map[form_id]
            case_updates = [update for update in get_case_updates(form) if update.id == self.case.case_id]
            types = [
                CaseTransaction.type_from_action_type_slug(a.action_type_slug)
                for case_update in case_updates
                for a in case_update.actions
            ]
            modified_on = case_updates[0].guess_modified_on()
            new_transaction = CaseTransaction.form_transaction(self.case, form, modified_on, types)
            transactions.append(new_transaction)

        def get_form(form_id):
            if form_id in updated_xforms_map:
                return updated_xforms_map[form_id]

            try:
                return xform_map[form_id]
            except KeyError:
                raise XFormNotFound(form_id)

        for case_transaction in transactions:
            if case_transaction.form_id:
                try:
                    case_transaction.cached_form = get_form(case_transaction.form_id)
                except XFormNotFound:
                    logging.error('Form not found during rebuild: %s', case_transaction.form_id)


def _transaction_sort_key_function(case):

    def transaction_cmp(first_transaction, second_transaction):
        # compare server dates if the forms aren't submitted by the same user
        if first_transaction.user_id != second_transaction.user_id:
            return cmp(first_transaction.server_date, second_transaction.server_date)

        if first_transaction.form_id and first_transaction.form_id == second_transaction.form_id:
            # short circuit if they are from the same form
            return cmp(
                type_index(first_transaction.type),
                type_index(second_transaction.type)
            )

        if not (first_transaction.server_date and second_transaction.server_date):
            raise MissingServerDate()

        if abs(first_transaction.server_date - second_transaction.server_date) > const.SIGNIFICANT_TIME:
            return cmp(first_transaction.server_date, second_transaction.server_date)

        return cmp(sort_key(first_transaction), sort_key(second_transaction))

    def type_index(action_type):
        """Consistent ordering for action types"""
        for idx, type_action in enumerate(CaseTransaction.FORM_TYPE_ACTIONS_ORDER):
            if action_type & type_action == action_type:
                return idx
        return len(CaseTransaction.FORM_TYPE_ACTIONS_ORDER)

    def sort_key(transaction):
        # if the user is the same you should compare with the special logic below
        return (
            transaction.client_date,
            form_index(transaction.form_id),
            type_index(transaction.type),
        )

    class cache(object):
        ids = None

    def form_index(form_id):
        if cache.ids is None:
            cache.ids = {form_id: i for i, form_id in enumerate(case.xform_ids)}
        return cache.ids.get(form_id, sys.maxsize)

    return cmp_to_key(transaction_cmp)
