from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.messaging.scheduling.util import utcnow
from corehq.messaging.tasks import get_sync_key
from corehq.util.log import with_progress_bar
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import CriticalSection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Runs a messaging rule against all cases for the domain/case_type"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('rule_id', type=int)

    def get_rule(self, domain, rule_id):
        try:
            rule = AutomaticUpdateRule.objects.get(pk=rule_id)
        except AutomaticUpdateRule.DoesNotExist:
            raise CommandError("Rule not found")

        if rule.domain != domain:
            raise CommandError("Domain '%s' does not match rule's domain '%s'" % (domain, rule.domain))

        if rule.workflow != AutomaticUpdateRule.WORKFLOW_SCHEDULING:
            raise CommandError("Expected the rule to be a messaging rule")

        return rule

    def handle(self, **options):
        rule = self.get_rule(options['domain'], options['rule_id'])

        print("Fetching case ids...")
        case_ids = CaseAccessors(rule.domain).get_case_ids_in_domain(rule.case_type)
        case_id_chunks = list(chunked(case_ids, 10))

        for case_id_chunk in with_progress_bar(case_id_chunks):
            case_id_chunk = list(case_id_chunk)
            with CriticalSection([get_sync_key(case_id) for case_id in case_id_chunk], timeout=5 * 60):
                for case in CaseAccessors(rule.domain).get_cases(case_id_chunk):
                    rule.run_rule(case, utcnow())
