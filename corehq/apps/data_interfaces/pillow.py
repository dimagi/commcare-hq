from datetime import datetime

from casexml.apps.case.xform import get_case_updates
from pillowtop.processors import PillowProcessor

from corehq.apps.data_interfaces.deduplication import is_dedupe_xmlns
from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CaseDeduplicationActionDefinition
from corehq.apps.data_interfaces.utils import run_rules_for_case
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.models.forms import XFormInstance
from corehq.apps.hqcase.constants import UPDATE_REASON_RESAVE
from corehq.util.soft_assert import soft_assert

from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE


class CaseDeduplicationProcessor(PillowProcessor):
    """Runs Case Deduplication actions whenever a user submits a form

    Reads from:
    - Elasticsearch (one search per case)
    - Update Rules

    Writes to:
    - Postgres (marking cases as duplicate)
    - Cases (through case updates)
    """

    def process_change(self, change):
        domain = change.metadata.domain

        if change.deleted:
            # TODO: If a case gets deleted, we don't remove the duplicates for this case?
            return

        if self._is_system_change(change):
            # Duplicates are meant to surface user duplicates, not system ones
            return

        rules = self._get_applicable_rules(change)
        if not rules:
            return

        case = CommCareCase.objects.get_case(change.id, domain)
        return run_rules_for_case(case, rules, datetime.utcnow())

    @staticmethod
    def _is_system_change(change):
        # This is an incomplete list of system changes.
        # USER_LOCATION_OWNER_MAP_TYPE was important to exclude because the associated form
        # is often not present. Other types can be freely added to make processing more efficient
        if change.metadata.document_subtype == USER_LOCATION_OWNER_MAP_TYPE:
            case = CommCareCase.objects.get_case(change.id, change.metadata.domain)
            # Nothing prevents a user from creating a USER_LOCATION_OWNER_MAP_TYPE. However, these
            # user-created cases will have their opened_by property set, whereas authentic CommTrack ones will not
            if not case.opened_by:
                return True

        return False

    def _get_applicable_rules(self, change):
        domain = change.metadata.domain
        associated_form_id = change.metadata.associated_document_id

        # TODO: feels like there should be some enforced order for running through rules?
        rules = self._get_rules(domain)

        if not associated_form_id or associated_form_id == UPDATE_REASON_RESAVE:
            # no associated form occurs whenever a form is rebuilt. Forms can be rebuilt
            # when a deletion is being undone or a form is being restored. In either case,
            # all rules may be interested in these changes
            applicable_rules = rules
        else:
            associated_form = self._get_associated_form(change)
            if associated_form and not is_dedupe_xmlns(associated_form.xmlns):
                case_updates = get_case_updates(associated_form, for_case=change.id)
                applicable_rules = [rule for rule in rules if self._has_applicable_changes(case_updates, rule)]
            else:
                applicable_rules = []

        return applicable_rules

    def _get_rules(self, domain):
        return AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

    def _get_associated_form(self, change):
        associated_form_id = change.metadata.associated_document_id
        associated_form = None
        if associated_form_id:
            try:
                associated_form = XFormInstance.objects.get_form(associated_form_id)
            except XFormNotFound:
                _assert = soft_assert(['mriley_at_dimagi_dot_com'.replace('_at_', '@').replace('_dot_', '.')])
                _assert(False, 'Associated form not found', {
                    'case_id': change.id,
                    'form_id': associated_form_id
                })
                associated_form = None

        return associated_form

    def _has_applicable_changes(self, case_updates, rule):
        action_definition = CaseDeduplicationActionDefinition.from_rule(rule)
        if not action_definition.include_closed:
            # If the rule shouldn't include closed cases, then a case being closed is an actionable event
            closes_case = any(case_update.closes_case() for case_update in case_updates)
            if closes_case:
                return True

        changed_properties_iter = (
            case_update.get_normalized_update_property_names() for case_update in case_updates
        )
        return any(
            action_definition.properties_fit_definition(properties) for properties in changed_properties_iter
        )
