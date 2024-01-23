from datetime import datetime

from casexml.apps.case.xform import get_case_updates
from pillowtop.processors import PillowProcessor

from corehq.apps.data_interfaces.deduplication import is_dedupe_xmlns
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.form_processor.exceptions import XFormNotFound
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.models.forms import XFormInstance
from corehq.toggles import CASE_DEDUPE
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
        if not CASE_DEDUPE.enabled(domain):
            return

        if change.deleted:
            return

        associated_form = self._get_associated_form(change)
        if not associated_form or is_dedupe_xmlns(associated_form.xmlns):
            return

        rules = self._get_rules(domain)
        if not rules:
            return

        for case_update in get_case_updates(associated_form, for_case=change.id):
            self._process_case_update(domain, case_update)

    def _get_rules(self, domain):
        return AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

    def _process_case_update(self, domain, case_update):
        changed_properties = case_update.get_normalized_update_property_names()

        for rule in self._get_rules(domain):
            for action in rule.memoized_actions:
                self._process_action(domain, rule, action, changed_properties, case_update.id)

    def _process_action(self, domain, rule, action, changed_properties, case_id):
        if action.definition.properties_fit_definition(changed_properties):
            case = CommCareCase.objects.get_case(case_id, domain)
            if case.type == rule.case_type:
                rule.run_rule(case, datetime.utcnow())

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
