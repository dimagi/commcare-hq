from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.domain.models import Domain
from corehq.messaging.management.commands.export_conditional_alerts import (
    SimpleSchedulingRule,
    SimpleSMSDailyScheduleWithTime,
    SimpleSMSAlertSchedule,
    SIMPLE_SMS_DAILY_SCHEDULE_WITH_TIME,
    SIMPLE_SMS_ALERT_SCHEDULE,
)
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    TimedSchedule,
    TimedEvent,
    SMSContent,
)
from corehq.messaging.tasks import initiate_messaging_rule_run
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import json


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('filename')

    def handle(self, domain, filename, **options):
        domain_obj = Domain.get_by_name(domain)
        if domain_obj is None:
            raise CommandError("Project space '%s' not found" % domain)

        if not domain_obj.uses_new_reminders:
            raise CommandError("Project space '%s' does not have new reminders enabled" % domain)

        json_rules = []
        with open(filename, 'rb') as f:
            for line in f:
                json_rules.append(json.loads(line))

        print("Importing %s rules..." % len(json_rules))

        rules = []
        with transaction.atomic():
            for entry in json_rules:
                json_rule = SimpleSchedulingRule(entry['rule'])

                schedule_type = entry['schedule']['schedule_type']
                if schedule_type == SIMPLE_SMS_DAILY_SCHEDULE_WITH_TIME:
                    json_schedule = SimpleSMSDailyScheduleWithTime(entry['schedule'])
                    schedule = TimedSchedule.create_simple_daily_schedule(
                        domain,
                        TimedEvent(time=json_schedule.time),
                        SMSContent(message=json_schedule.message),
                        total_iterations=json_schedule.total_iterations,
                        start_offset=json_schedule.start_offset,
                        start_day_of_week=json_schedule.start_day_of_week,
                        extra_options=json_schedule.extra_options.to_json(),
                        repeat_every=json_schedule.repeat_every,
                    )
                elif schedule_type == SIMPLE_SMS_ALERT_SCHEDULE:
                    json_schedule = SimpleSMSAlertSchedule(entry['schedule'])
                    schedule = AlertSchedule.create_simple_alert(
                        domain,
                        SMSContent(message=json_schedule.message),
                        extra_options=json_schedule.extra_options.to_json(),
                    )
                else:
                    raise CommandError("Unexpected schedule_type: %s" % schedule_type)

                rule = AutomaticUpdateRule.objects.create(
                    domain=domain,
                    name=json_rule.name,
                    case_type=json_rule.case_type,
                    active=True,
                    filter_on_server_modified=False,
                    migrated=True,
                    workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                )

                for criterion in json_rule.criteria:
                    rule.add_criteria(
                        MatchPropertyDefinition,
                        property_name=criterion.property_name,
                        property_value=criterion.property_value,
                        match_type=criterion.match_type,
                    )

                rule.add_action(
                    CreateScheduleInstanceActionDefinition,
                    alert_schedule_id=schedule.schedule_id if isinstance(schedule, AlertSchedule) else None,
                    timed_schedule_id=schedule.schedule_id if isinstance(schedule, TimedSchedule) else None,
                    recipients=json_rule.recipients,
                    reset_case_property_name=json_rule.reset_case_property_name,
                    start_date_case_property=json_rule.start_date_case_property,
                    specific_start_date=json_rule.specific_start_date,
                    scheduler_module_info=json_rule.scheduler_module_info.to_json(),
                )

                rules.append(rule)

        print("Import complete. Starting instance refresh tasks...")

        for rule in rules:
            initiate_messaging_rule_run(rule.domain, rule.pk)

        print("Done.")
