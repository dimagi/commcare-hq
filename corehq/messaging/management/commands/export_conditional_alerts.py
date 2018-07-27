from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.messaging.scheduling.models import (
    Schedule,
    AlertSchedule,
    TimedSchedule,
    TimedEvent,
    SMSContent,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import CaseScheduleInstanceMixin
from django.core.management.base import BaseCommand, CommandError
import copy
import json
import jsonobject
import six


SIMPLE_SMS_DAILY_SCHEDULE_WITH_TIME = 1
SIMPLE_SMS_ALERT_SCHEDULE = 2


class MatchPropertyCriterion(jsonobject.JsonObject):
    property_name = jsonobject.StringProperty()
    property_value = jsonobject.StringProperty()
    match_type = jsonobject.StringProperty()


class SimpleSchedulingRule(jsonobject.JsonObject):
    name = jsonobject.StringProperty()
    case_type = jsonobject.StringProperty()
    criteria = jsonobject.ListProperty(MatchPropertyCriterion)
    recipients = jsonobject.ListProperty(jsonobject.ListProperty(jsonobject.StringProperty(required=False)))
    reset_case_property_name = jsonobject.StringProperty()
    start_date_case_property = jsonobject.StringProperty()
    specific_start_date = jsonobject.DateProperty()
    scheduler_module_info = jsonobject.ObjectProperty(CreateScheduleInstanceActionDefinition.SchedulerModuleInfo)


class ExtraSchedulingOptions(jsonobject.JsonObject):
    active = jsonobject.BooleanProperty()
    include_descendant_locations = jsonobject.BooleanProperty()
    default_language_code = jsonobject.StringProperty()
    custom_metadata = jsonobject.DictProperty(six.text_type)
    use_utc_as_default_timezone = jsonobject.BooleanProperty()
    user_data_filter = jsonobject.DictProperty(jsonobject.ListProperty(six.text_type))
    stop_date_case_property_name = jsonobject.StringProperty()


class SimpleSMSDailyScheduleWithTime(jsonobject.JsonObject):
    schedule_type = SIMPLE_SMS_DAILY_SCHEDULE_WITH_TIME
    time = jsonobject.TimeProperty()
    message = jsonobject.DictProperty(six.text_type)
    total_iterations = jsonobject.IntegerProperty()
    start_offset = jsonobject.IntegerProperty()
    start_day_of_week = jsonobject.IntegerProperty()
    extra_options = jsonobject.ObjectProperty(ExtraSchedulingOptions)
    repeat_every = jsonobject.IntegerProperty()


class SimpleSMSAlertSchedule(jsonobject.JsonObject):
    schedule_type = SIMPLE_SMS_ALERT_SCHEDULE
    message = jsonobject.DictProperty(six.text_type)
    extra_options = jsonobject.ObjectProperty(ExtraSchedulingOptions)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def get_json_rule(self, rule):
        json_rule = SimpleSchedulingRule(
            name=rule.name,
            case_type=rule.case_type,
        )

        for criterion in rule.memoized_criteria:
            definition = criterion.definition
            if not isinstance(definition, MatchPropertyDefinition):
                raise CommandError(
                    "Rule %s references currently unsupported criterion definition for export." % rule.pk
                )

            json_rule.criteria.append(MatchPropertyCriterion(
                property_name=definition.property_name,
                property_value=definition.property_value,
                match_type=definition.match_type,
            ))

        if len(rule.memoized_actions) != 1:
            raise CommandError("Expected exactly one action for rule %s" % rule.pk)

        action = rule.memoized_actions[0].definition
        if not isinstance(action, CreateScheduleInstanceActionDefinition):
            raise CommandError("Expected CreateScheduleInstanceActionDefinition")

        for recipient_type, recipient_id in action.recipients:
            if recipient_type not in (
                CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF,
                CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER,
                CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER,
                CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE,
                CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM,
            ):
                raise CommandError("Unexpected recipient_type in rule %s" % rule.pk)

        if action.get_scheduler_module_info().enabled:
            raise CommandError("Expected scheduler module integration to be disabled")

        json_rule.recipients = copy.deepcopy(action.recipients)
        reset_case_property_name = action.reset_case_property_name
        start_date_case_property = action.start_date_case_property
        specific_start_date = action.specific_start_date
        scheduler_module_info = CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(enabled=False)

        return json_rule

    def get_json_scheduling_options(self, schedule):
        return ExtraSchedulingOptions(
            active=schedule.active,
            include_descendant_locations=schedule.include_descendant_locations,
            default_language_code=schedule.default_language_code,
            custom_metadata=copy.deepcopy(schedule.custom_metadata),
            use_utc_as_default_timezone=schedule.use_utc_as_default_timezone,
            user_data_filter=copy.deepcopy(schedule.user_data_filter),
            stop_date_case_property_name=schedule.stop_date_case_property_name,
        )

    def get_json_timed_schedule(self, schedule):
        if schedule.ui_type != Schedule.UI_TYPE_DAILY:
            raise CommandError("Expected simple daily schedule")

        json_schedule = SimpleSMSDailyScheduleWithTime(
            total_iterations=schedule.total_iterations,
            start_offset=schedule.start_offset,
            start_day_of_week=schedule.start_day_of_week,
            repeat_every=schedule.repeat_every,
            extra_options=self.get_json_scheduling_options(schedule),
        )

        event = schedule.memoized_events[0]
        if not isinstance(event, TimedEvent):
            raise CommandError("Expected TimedEvent")

        json_schedule.time = event.time

        content = event.content
        if not isinstance(content, SMSContent):
            raise CommandError("Expected SMSContent")

        json_schedule.message = copy.deepcopy(content.message)

        return json_schedule

    def get_json_alert_schedule(self, schedule):
        if schedule.ui_type != Schedule.UI_TYPE_IMMEDIATE:
            raise CommandError("Expected simple immediate schedule")

        json_schedule = SimpleSMSAlertSchedule(
            extra_options=self.get_json_scheduling_options(schedule),
        )

        event = schedule.memoized_events[0]
        content = event.content
        if not isinstance(content, SMSContent):
            raise CommandError("Expected SMSContent")

        json_schedule.message = copy.deepcopy(content.message)

        return json_schedule

    def handle(self, domain, **options):
        result = []
        for rule in AutomaticUpdateRule.by_domain(
            domain,
            AutomaticUpdateRule.WORKFLOW_SCHEDULING,
            active_only=False,
        ):
            json_rule = self.get_json_rule(rule)

            action = rule.memoized_actions[0].definition
            if action.schedule.location_type_filter:
                raise CommandError("Expected location_type_filter to be empty for rule %s" % rule.pk)

            if isinstance(action.schedule, TimedSchedule):
                json_schedule = self.get_json_timed_schedule(action.schedule)
            elif isinstance(action.schedule, AlertSchedule):
                json_schedule = self.get_json_alert_schedule(action.schedule)
            else:
                raise CommandError("Unexpected Schedule type for rule %s" % rule.pk)

            result.append(json.dumps({
                'rule': json_rule.to_json(),
                'schedule': json_schedule.to_json(),
            }))

        with open('conditional_alerts_for_%s.txt' % domain, 'wb') as f:
            for line in result:
                f.write(line)
                f.write('\n')

        print("Done")
