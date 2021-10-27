from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.messaging.util import MessagingRuleProgressHelper
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = """
        Check status of and cancel currently-running AutomaticUpdateRule runs.
        If domain and rule-id are given, will check on and optionally cancel that rule.
        If no arguments are passed, will display status of all currently locked rules.
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain',
            help='Required if passing rule-id. Acts as a sanity check while fetching given rule.'
        )
        parser.add_argument(
            '--rule-id',
            help='If provided, fetch status for only this rule',
        )
        parser.add_argument(
            '--cancel',
            action='store_true',
            default=False,
            help='Cancel the given rule',
        )

    def get_rule(self, domain, rule_id):
        try:
            rule = AutomaticUpdateRule.objects.get(pk=rule_id)
        except AutomaticUpdateRule.DoesNotExist:
            raise CommandError("Rule not found")

        if rule.domain != domain:
            raise CommandError("Domain '%s' does not match rule's domain '%s'" % (domain, rule.domain))

        if rule.workflow not in [
                AutomaticUpdateRule.WORKFLOW_SCHEDULING, AutomaticUpdateRule.WORKFLOW_DEDUPLICATE]:
            raise CommandError("Expected the rule to be a messaging or deduplicate rule")

        return rule

    def print_status(self, rule):
        schedule = rule.get_schedule()
        msg = MessagingRuleProgressHelper(rule.id)
        initiated = msg.rule_initiation_key_is_set()
        processed = msg.client.get(msg.current_key)
        total = msg.client.get(msg.total_key)
        print("{}: ({}) {:<25}  {} / {} processed, {}m to reset{}".format(
            rule.id,
            ", ".join([
                "rule " + ("on" if rule.active else "off"),
                "schedule " + ("on" if schedule.active else "off"),
                ("lock" if rule.locked_for_editing else "edit"),
            ]),
            rule.name,
            processed,
            total,
            (msg.rule_initiation_key_minutes_remaining() if initiated else "?"),
            (", canceled" if msg.is_canceled() else ""),
        ))

    def handle(self, rule_id=None, domain=None, cancel=False, **options):
        rule = None

        if rule_id and domain:
            rule = self.get_rule(domain, rule_id)
            self.print_status(rule)

            if cancel:
                confirm = input("Are you sure you want to cancel this rule?  This is NOT a dry run. y/N?")
                if confirm == "y":
                    msg = MessagingRuleProgressHelper(rule.id)
                    if msg.is_canceled():
                        print("already canceled")
                    else:
                        msg.cancel()
                        print("canceled rule", rule_id)
        else:
            print("Currently locked rules:")
            rules = AutomaticUpdateRule.objects.filter(locked_for_editing=True)
            for rule in rules:
                self.print_status(rule)
