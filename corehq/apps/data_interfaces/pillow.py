from datetime import datetime

from casexml.apps.case.xform import get_case_updates
from pillowtop.processors import PillowProcessor

from corehq.apps.data_interfaces.models import (
    DEDUPE_XMLNS,
    AutomaticUpdateRule,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.toggles import CASE_DEDUPE


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

        if change.get_document().get('xmlns') == DEDUPE_XMLNS:
            return

        rules = self._get_rules(domain)
        if not rules:
            return

        for case_update in get_case_updates(change.get_document()):
            self._process_case_update(domain, case_update)

    def _get_rules(self, domain):
        return AutomaticUpdateRule.by_domain_cached(domain, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)

    def _process_case_update(self, domain, case_update):
        changed_properties = set()
        if case_update.get_create_action() is not None:
            changed_properties.update(set(case_update.get_create_action().raw_block.keys()))
        if case_update.get_update_action() is not None:
            changed_properties.update(set(case_update.get_update_action().raw_block.keys()))

        for rule in self._get_rules(domain):
            for action in rule.memoized_actions:
                self._process_action(domain, rule, action, changed_properties, case_update.id)

    def _process_action(self, domain, rule, action, changed_properties, case_id):
        if action.definition.properties_fit_definition(changed_properties):
            try:
                case = CaseAccessors(domain).get_case(case_id)
            except CaseNotFound:
                return

            if case.type == rule.case_type:
                rule.run_rule(case, datetime.utcnow())
