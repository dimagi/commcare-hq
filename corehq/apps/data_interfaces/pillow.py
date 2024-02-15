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

        rules = self._get_applicable_rules(change)
        if not rules:
            return

        case = CommCareCase.objects.get_case(change.id, domain)
        return run_rules_for_case(case, rules, datetime.utcnow())

    def _get_applicable_rules(self, change):
        domain = change.metadata.domain
        associated_form_id = change.metadata.associated_document_id

        if not associated_form_id:
            return []

        # TODO: feels like there should be some enforced order for running through rules?
        rules = self._get_rules(domain)

        if associated_form_id == UPDATE_REASON_RESAVE:
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
        changed_properties_iter = (
            case_update.get_normalized_update_property_names() for case_update in case_updates
        )
        return any(
            action_definition.properties_fit_definition(properties) for properties in changed_properties_iter
        )
