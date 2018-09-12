from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.couch_sql_migration.progress import couch_sql_migration_in_progress
from corehq.apps.domain.models import Domain
from corehq.apps.reminders.models import (
    CaseReminder,
    CaseReminderHandler,
    REMINDER_TYPE_DEFAULT,
    REMINDER_TYPE_ONE_TIME,
    REMINDER_TYPE_KEYWORD_INITIATED,
    REMINDER_TYPE_SURVEY_MANAGEMENT,
    UI_SIMPLE_FIXED,
    EVENT_AS_OFFSET,
    EVENT_AS_SCHEDULE,
    FIRE_TIME_DEFAULT,
    FIRE_TIME_CASE_PROPERTY,
    FIRE_TIME_RANDOM,
    METHOD_SMS,
    METHOD_SMS_CALLBACK,
    METHOD_SMS_SURVEY,
    METHOD_IVR_SURVEY,
    METHOD_EMAIL,
    RECIPIENT_USER,
    RECIPIENT_OWNER,
    RECIPIENT_CASE,
    RECIPIENT_SURVEY_SAMPLE,
    RECIPIENT_PARENT_CASE,
    RECIPIENT_SUBCASE,
    RECIPIENT_USER_GROUP,
    RECIPIENT_LOCATION,
    CASE_CRITERIA,
    ON_DATETIME,
    MATCH_EXACT,
    MATCH_REGEX,
    MATCH_ANY_VALUE,
    DAY_ANY,
)
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    AlertEvent,
    ImmediateBroadcast,
    TimedSchedule,
    TimedEvent,
    RandomTimedEvent,
    CasePropertyTimedEvent,
    SMSContent,
    EmailContent,
    SMSSurveyContent,
    IVRSurveyContent,
    SMSCallbackContent,
    MigratedReminder,
    CustomContent,
)
from corehq.messaging.scheduling.tasks import refresh_alert_schedule_instances
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    ScheduleInstance,
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseScheduleInstanceMixin,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.tasks import initiate_messaging_rule_run
from corehq.messaging.util import project_is_on_new_reminders
from corehq.sql_db.util import run_query_across_partitioned_databases
from corehq.toggles import REMINDERS_MIGRATION_IN_PROGRESS
from datetime import time, datetime, timedelta
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.core.management.base import BaseCommand
from six import moves
from time import sleep
from io import open


CUSTOM_RECIPIENTS = (
    'CASE_OWNER_LOCATION_PARENT',
    'HOST_CASE_OWNER_LOCATION',
    'HOST_CASE_OWNER_LOCATION_PARENT',
)


def log(message):
    print(message)
    with open('new_reminders_migration.log', 'a', encoding='utf-8') as f:
        f.write(message)
        f.write('\n')


class BaseMigrator(object):

    def migrate(self):
        raise NotImplementedError

    def migrate_schedule_instances(self):
        raise NotImplementedError

    def refresh_schedule_instances(self):
        raise NotImplementedError

    def get_alert_schedule_instance_class(self):
        raise NotImplementedError

    def get_timed_schedule_instance_class(self):
        raise NotImplementedError

    def print_migrator_specific_info(self):
        raise NotImplementedError

    def log_migrated_reminder(self):
        raise NotImplementedError

    def get_source_instances(self):
        return list(CaseReminder.view(
            'reminders/by_domain_handler_case',
            startkey=[self.handler.domain, self.handler._id],
            endkey=[self.handler.domain, self.handler._id, {}],
            include_docs=True
        ).all())

    def get_target_instances(self):
        if isinstance(self.schedule, AlertSchedule):
            return list(run_query_across_partitioned_databases(
                self.get_alert_schedule_instance_class(),
                Q(alert_schedule_id=self.schedule.schedule_id),
            ))
        elif isinstance(self.schedule, TimedSchedule):
            return list(run_query_across_partitioned_databases(
                self.get_timed_schedule_instance_class(),
                Q(timed_schedule_id=self.schedule.schedule_id),
            ))
        else:
            raise TypeError("Expected AlertSchedule or TimedSchedule")

    def set_target_instance_info(self, target_instances):
        self.target_instance_info = {}
        for i in target_instances:
            info = {
                'recipient_type': i.recipient_type,
                'recipient_id': i.recipient_id,
                'active': i.active,
                'current_event_num': i.current_event_num,
                'schedule_iteration_num': i.schedule_iteration_num,
            }

            if isinstance(i, CaseScheduleInstanceMixin):
                info['case_id'] = i.case_id

            if isinstance(self.schedule, TimedSchedule):
                info['start_date'] = i.start_date

            if not (
                isinstance(self.schedule, TimedSchedule) and
                self.schedule.event_type == TimedSchedule.EVENT_RANDOM_TIME
            ):
                info['next_event_due'] = i.next_event_due

            self.target_instance_info[i.schedule_instance_id] = info

    def print_status(self):
        source_instances = self.get_source_instances()
        target_instances = self.get_target_instances()

        source_instance_count = len(source_instances)
        active_source_instance_count = len([i for i in source_instances if i.active])
        target_instance_count = len(target_instances)
        active_target_instance_count = len([i for i in target_instances if i.active])

        self.set_target_instance_info(target_instances)

        log("\n")
        self.print_migrator_specific_info()
        log("Source Count:        %s" % source_instance_count)
        log("Target Count:        %s" % target_instance_count)
        log("Source Active Count: %s" % active_source_instance_count)
        log("Target Active Count: %s" % active_target_instance_count)


class CaseReminderHandlerMigrator(BaseMigrator):

    def __init__(self, handler, rule_migration_function, schedule_migration_function, until_references_timestamp):
        self.handler = handler
        self.rule_migration_function = rule_migration_function
        self.schedule_migration_function = schedule_migration_function
        self.until_references_timestamp = until_references_timestamp
        self.source_duplicate_count = 0

    def migrate(self):
        with transaction.atomic():
            self.schedule = self.schedule_migration_function(self.handler, self)
            self.rule = self.rule_migration_function(self.handler, self.schedule, self.until_references_timestamp)

    def log_migrated_reminder(self):
        obj, _ = MigratedReminder.objects.get_or_create(handler_id=self.handler._id)
        obj.rule = self.rule
        obj.broadcast = None
        obj.save()

    def migrate_schedule_instances(self):
        if isinstance(self.schedule, AlertSchedule):
            self.migrate_case_alert_schedule_instances()
        elif isinstance(self.schedule, TimedSchedule):
            self.migrate_case_timed_schedule_instances()
        else:
            raise TypeError("Unknown schedule type")

    def migrate_case_alert_schedule_instances(self):
        seen_case_ids = set()
        recipient = self.rule.memoized_actions[0].definition.recipients[0]

        for reminder in self.get_source_instances():
            if reminder.case_id in seen_case_ids:
                self.source_duplicate_count += 1
                continue

            seen_case_ids.add(reminder.case_id)

            instance = CaseAlertScheduleInstance(
                domain=self.rule.domain,
                recipient_type=recipient[0],
                recipient_id=recipient[1],
                current_event_num=reminder.current_event_sequence_num,
                schedule_iteration_num=reminder.schedule_iteration_num,
                next_event_due=reminder.next_fire,
                active=reminder.active,
                alert_schedule_id=self.schedule.schedule_id,
                case_id=reminder.case_id,
                rule_id=self.rule.pk,
            )

            if reminder.active and reminder.error:
                self.schedule.move_to_next_event_not_in_the_past(instance)

            instance.save(force_insert=True)

    def migrate_case_timed_schedule_instances(self):
        seen_case_ids = set()
        recipient = self.rule.memoized_actions[0].definition.recipients[0]

        for reminder in self.get_source_instances():
            if reminder.case_id in seen_case_ids:
                self.source_duplicate_count += 1
                continue

            seen_case_ids.add(reminder.case_id)

            instance = CaseTimedScheduleInstance(
                domain=self.rule.domain,
                recipient_type=recipient[0],
                recipient_id=recipient[1],
                current_event_num=reminder.current_event_sequence_num,
                schedule_iteration_num=reminder.schedule_iteration_num,
                next_event_due=reminder.next_fire,
                active=reminder.active,
                timed_schedule_id=self.schedule.schedule_id,
                start_date=reminder.start_date,
                case_id=reminder.case_id,
                rule_id=self.rule.pk,
            )

            if reminder.active and reminder.error:
                self.schedule.move_to_next_event_not_in_the_past(instance)

            instance.save(force_insert=True)

    def get_alert_schedule_instance_class(self):
        return CaseAlertScheduleInstance

    def get_timed_schedule_instance_class(self):
        return CaseTimedScheduleInstance

    def print_migrator_specific_info(self):
        log("--- CaseReminderHandler %s to AutomaticUpdateRule %s ---" % (self.handler._id, self.rule.pk))
        log("Duplicates:          %s" % self.source_duplicate_count)

    def refresh_schedule_instances(self):
        initiate_messaging_rule_run(self.rule.domain, self.rule.pk)


class ManualCaseReminderHandlerMigrator(CaseReminderHandlerMigrator):

    def __init__(self, handler, rule_id):
        self.handler = handler
        self.source_duplicate_count = 0

        try:
            self.rule = AutomaticUpdateRule.objects.get(
                pk=rule_id,
                domain=handler.domain,
                workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
                deleted=False,
            )
        except AutomaticUpdateRule.DoesNotExist:
            raise ValueError("Invalid rule_id given: %s" % rule_id)

        self.schedule = self.rule.get_messaging_rule_schedule()

    def migrate(self):
        pass


class BroadcastMigrator(BaseMigrator):

    def __init__(self, handler, broadcast_migration_function):
        self.handler = handler
        self.broadcast_migration_function = broadcast_migration_function

    def migrate(self):
        with transaction.atomic():
            self.broadcast, self.schedule = self.broadcast_migration_function(self.handler, self)

    def log_migrated_reminder(self):
        obj, _ = MigratedReminder.objects.get_or_create(handler_id=self.handler._id)
        obj.broadcast = self.broadcast
        obj.rule = None
        obj.save()

    def migrate_schedule_instances(self):
        if not isinstance(self.schedule, AlertSchedule):
            raise TypeError("Expected AlertSchedule")

        for recipient in self.broadcast.recipients:
            instance = AlertScheduleInstance(
                domain=self.broadcast.domain,
                recipient_type=recipient[0],
                recipient_id=recipient[1],
                current_event_num=0,
                schedule_iteration_num=2,
                next_event_due=self.handler.start_datetime,
                active=False,
                alert_schedule_id=self.schedule.schedule_id,
            )

            instance.save(force_insert=True)

    def get_alert_schedule_instance_class(self):
        return AlertScheduleInstance

    def get_timed_schedule_instance_class(self):
        return TimedScheduleInstance

    def print_migrator_specific_info(self):
        log(
            "--- CaseReminderHandler %s to %s %s ---" % (
                self.handler._id,
                self.broadcast.__class__.__name__,
                self.broadcast.pk,
            )
        )

    def refresh_schedule_instances(self):
        if not isinstance(self.schedule, AlertSchedule):
            raise TypeError("Expected AlertSchedule")

        refresh_alert_schedule_instances(self.schedule.schedule_id, self.broadcast.recipients)


def get_extra_scheduling_options(handler, migrator, translated=True, include_utc_option=False):
    if handler.reminder_type == REMINDER_TYPE_DEFAULT and handler.include_child_locations:
        raise ValueError("Unexpected value for include_child_locations for %s" % handler._id)

    result = {
        'active': handler.active,
        'default_language_code': handler.default_lang if translated else None,
        'include_descendant_locations': handler.include_child_locations,
        'user_data_filter': handler.user_data_filter or {},
    }

    if isinstance(migrator, CaseReminderHandlerMigrator) and handler.until and migrator.until_references_timestamp:
        result['stop_date_case_property_name'] = handler.until

    if include_utc_option or ('stop_date_case_property_name' in result):
        result['use_utc_as_default_timezone'] = True

    return result


def check_days_until(message_dict):
    for lang, message in message_dict.items():
        if '.days_until' in message:
            raise ValueError(".days_until is not supported")


def get_single_dict_value(d):
    if len(d) != 1:
        raise ValueError("Expected exactly one entry")

    return list(d.values())[0]


def get_content(handler, event, translated=True):
    if handler.method == METHOD_SMS:
        if handler.custom_content_handler:
            return CustomContent(custom_content_id=handler.custom_content_handler)

        check_days_until(event.message)
        if translated:
            return SMSContent(message=event.message)
        else:
            return SMSContent(message={'*': get_single_dict_value(event.message)})
    elif handler.method == METHOD_EMAIL:
        check_days_until(event.subject)
        check_days_until(event.message)
        if translated:
            return EmailContent(subject=event.subject, message=event.message)
        else:
            return EmailContent(
                subject={'*': get_single_dict_value(event.subject)},
                message={'*': get_single_dict_value(event.message)},
            )
    elif handler.method == METHOD_SMS_SURVEY:
        if event.callback_timeout_intervals:
            if handler.submit_partial_forms:
                expire_after = sum(event.callback_timeout_intervals)
                reminder_intervals = event.callback_timeout_intervals[:-1]
            else:
                expire_after = SQLXFormsSession.MAX_SESSION_LENGTH
                reminder_intervals = event.callback_timeout_intervals

            submit_partially_completed_forms = handler.submit_partial_forms
            include_case_updates_in_partial_submissions = handler.include_case_side_effects
        else:
            expire_after = SQLXFormsSession.MAX_SESSION_LENGTH
            reminder_intervals = []
            submit_partially_completed_forms = False
            include_case_updates_in_partial_submissions = False

        return SMSSurveyContent(
            form_unique_id=event.form_unique_id,
            expire_after=expire_after,
            reminder_intervals=reminder_intervals,
            submit_partially_completed_forms=submit_partially_completed_forms,
            include_case_updates_in_partial_submissions=include_case_updates_in_partial_submissions,
        )
    elif handler.method == METHOD_IVR_SURVEY:
        return IVRSurveyContent(
            form_unique_id=event.form_unique_id,
            reminder_intervals=event.callback_timeout_intervals,
            submit_partially_completed_forms=handler.submit_partial_forms,
            include_case_updates_in_partial_submissions=handler.include_case_side_effects,
            max_question_attempts=handler.max_question_retries,
        )
    elif handler.method == METHOD_SMS_CALLBACK:
        if translated:
            message = event.message
        else:
            message = {'*': get_single_dict_value(event.message)}

        return SMSCallbackContent(
            message=message,
            reminder_intervals=event.callback_timeout_intervals,
        )
    else:
        raise ValueError("Unexpected method '%s'" % handler.method)


def get_timed_event(handler, event):
    if handler.event_interpretation != EVENT_AS_SCHEDULE:
        raise ValueError("Unexpected event_interpretation: %s" % handler.event_interpretation)

    if event.fire_time_type == FIRE_TIME_DEFAULT:
        return TimedEvent(
            day=event.day_num,
            time=event.fire_time,
        )
    elif event.fire_time_type == FIRE_TIME_RANDOM:
        return RandomTimedEvent(
            day=event.day_num,
            time=event.fire_time,
            window_length=event.time_window_length,
        )
    elif event.fire_time_type == FIRE_TIME_CASE_PROPERTY:
        return CasePropertyTimedEvent(
            day=event.day_num,
            case_property_name=event.fire_time_aux,
        )
    else:
        raise ValueError("Unexpected fire_time_type: %s" % event.fire_time_type)


def get_event(handler, event):
    if handler.event_interpretation == EVENT_AS_OFFSET:
        return AlertEvent(
            minutes_to_wait=(
                (event.day_num * 1440) + (event.fire_time.hour * 60) + event.fire_time.minute
            )
        )
    else:
        raise ValueError("Unexpected event_interpretation '%s'" % handler.event_interpretation)


def get_rule_recipients(handler):
    if handler.recipient == RECIPIENT_CASE:
        return [(CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF, None)]
    elif handler.recipient == RECIPIENT_OWNER:
        return [(CaseScheduleInstanceMixin.RECIPIENT_TYPE_CASE_OWNER, None)]
    elif handler.recipient == RECIPIENT_USER:
        return [(CaseScheduleInstanceMixin.RECIPIENT_TYPE_LAST_SUBMITTING_USER, None)]
    elif handler.recipient == RECIPIENT_PARENT_CASE:
        return [(CaseScheduleInstanceMixin.RECIPIENT_TYPE_PARENT_CASE, None)]
    elif handler.recipient == RECIPIENT_SUBCASE:
        return [(CaseScheduleInstanceMixin.RECIPIENT_TYPE_ALL_CHILD_CASES, None)]
    elif handler.recipient == RECIPIENT_USER_GROUP:
        return [(ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, handler.user_group_id)]
    elif handler.recipient in CUSTOM_RECIPIENTS:
        return [(CaseScheduleInstanceMixin.RECIPIENT_TYPE_CUSTOM, handler.recipient)]
    else:
        raise ValueError("Unexpected recipient: '%s'" % handler.recipient)


def get_broadcast_recipients(handler):
    if handler.recipient == RECIPIENT_SURVEY_SAMPLE:
        return [(ScheduleInstance.RECIPIENT_TYPE_CASE_GROUP, handler.sample_id)]
    elif handler.recipient == RECIPIENT_USER_GROUP:
        return [(ScheduleInstance.RECIPIENT_TYPE_USER_GROUP, handler.user_group_id)]
    elif handler.recipient == RECIPIENT_LOCATION:
        return [(ScheduleInstance.RECIPIENT_TYPE_LOCATION, location_id) for location_id in handler.location_ids]
    else:
        raise ValueError("Unexpected recipient: '%s'" % handler.recipient)


def migrate_rule(handler, schedule, until_references_timestamp):
    rule = AutomaticUpdateRule.objects.create(
        domain=handler.domain,
        name=handler.nickname,
        case_type=handler.case_type,
        active=True,
        deleted=False,
        filter_on_server_modified=False,
        server_modified_boundary=None,
        workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
    )
    if not handler.start_property:
        raise ValueError("Expected start_property")

    if not (handler.start_property == '_id' and handler.start_match_type == MATCH_ANY_VALUE):
        if handler.start_match_type == MATCH_ANY_VALUE:
            rule.add_criteria(
                MatchPropertyDefinition,
                property_name=handler.start_property,
                match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
            )
        elif handler.start_match_type == MATCH_EXACT:
            if not handler.start_value:
                raise ValueError("Expected start_value")

            rule.add_criteria(
                MatchPropertyDefinition,
                property_name=handler.start_property,
                property_value=handler.start_value,
                match_type=MatchPropertyDefinition.MATCH_EQUAL,
            )
        elif handler.start_match_type == MATCH_REGEX:
            if not handler.start_value:
                raise ValueError("Expected start_value")

            rule.add_criteria(
                MatchPropertyDefinition,
                property_name=handler.start_property,
                property_value=handler.start_value,
                match_type=MatchPropertyDefinition.MATCH_REGEX,
            )
        else:
            raise ValueError("Unexpected start_match_type '%s'" % handler.start_match_type)

    if handler.until and not until_references_timestamp:
        # A legacy option from the original framework which only checked two values, 'ok' or 'OK'
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name=handler.until,
            property_value='ok',
            match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
        )
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name=handler.until,
            property_value='OK',
            match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
        )

    rule.add_action(
        CreateScheduleInstanceActionDefinition,
        alert_schedule_id=schedule.schedule_id if isinstance(schedule, AlertSchedule) else None,
        timed_schedule_id=schedule.schedule_id if isinstance(schedule, TimedSchedule) else None,
        recipients=get_rule_recipients(handler),
        start_date_case_property=handler.start_date,
    )
    return rule


def migrate_simple_alert_schedule(handler, migrator):
    return AlertSchedule.create_simple_alert(
        handler.domain,
        get_content(handler, handler.events[0]),
        extra_options=get_extra_scheduling_options(handler, migrator),
    )


def migrate_simple_daily_schedule(handler, migrator):
    return TimedSchedule.create_simple_daily_schedule(
        handler.domain,
        get_timed_event(handler, handler.events[0]),
        get_content(handler, handler.events[0]),
        total_iterations=handler.max_iteration_count,
        start_offset=handler.start_offset,
        extra_options=get_extra_scheduling_options(handler, migrator, include_utc_option=True),
        repeat_every=handler.schedule_length,
    )


def migrate_simple_weekly_schedule(handler, migrator):
    if handler.schedule_length > 0 and (handler.schedule_length % 7) == 0:
        repeat_every = handler.schedule_length // 7
    elif handler.max_iteration_count == 1:
        repeat_every = 1
    else:
        raise ValueError("Unable to convert schedule_length for handler %s" % handler._id)

    return TimedSchedule.create_simple_weekly_schedule(
        handler.domain,
        get_timed_event(handler, handler.events[0]),
        get_content(handler, handler.events[0]),
        [handler.start_day_of_week],
        handler.start_day_of_week,
        total_iterations=handler.max_iteration_count,
        extra_options=get_extra_scheduling_options(handler, migrator, include_utc_option=True),
        repeat_every=repeat_every,
    )


def get_offset_based_start_date_schedule_migration_function(repeat_every_override):

    def migrate_offset_based_start_date_schedule(handler, migrator):
        base_datetime = datetime(2000, 1, 1)
        running_datetime = datetime(2000, 1, 1)

        event_and_content_objects = []
        for event in handler.events:
            running_datetime += timedelta(days=event.day_num)
            running_datetime += timedelta(hours=event.fire_time.hour)
            running_datetime += timedelta(minutes=event.fire_time.minute)

            event_and_content_objects.append((
                TimedEvent(
                    day=(running_datetime - base_datetime).days,
                    time=running_datetime.time(),
                ),
                get_content(handler, event)
            ))

        if handler.max_iteration_count == 1:
            repeat_every = event_and_content_objects[-1][0].day + 1
        elif repeat_every_override:
            repeat_every = repeat_every_override
        else:
            raise ValueError("Expected repeat_every_override")

        if len(event_and_content_objects) == 1 and event_and_content_objects[0][0].day == 0:
            return TimedSchedule.create_simple_daily_schedule(
                handler.domain,
                event_and_content_objects[0][0],
                event_and_content_objects[0][1],
                total_iterations=handler.max_iteration_count,
                start_offset=handler.start_offset,
                extra_options=get_extra_scheduling_options(handler, migrator, include_utc_option=True),
                repeat_every=repeat_every,
            )
        else:
            return TimedSchedule.create_custom_daily_schedule(
                handler.domain,
                event_and_content_objects,
                total_iterations=handler.max_iteration_count,
                start_offset=handler.start_offset,
                extra_options=get_extra_scheduling_options(handler, migrator, include_utc_option=True),
                repeat_every=repeat_every,
            )

    return migrate_offset_based_start_date_schedule


def migrate_custom_daily_schedule(handler, migrator):
    return TimedSchedule.create_custom_daily_schedule(
        handler.domain,
        [(get_timed_event(handler, event), get_content(handler, event)) for event in handler.events],
        total_iterations=handler.max_iteration_count,
        start_offset=handler.start_offset,
        extra_options=get_extra_scheduling_options(handler, migrator, include_utc_option=True),
        repeat_every=handler.schedule_length,
    )


def migrate_custom_alert_schedule(handler, migrator):
    return AlertSchedule.create_custom_alert(
        handler.domain,
        [(get_event(handler, event), get_content(handler, event)) for event in handler.events],
        extra_options=get_extra_scheduling_options(handler, migrator),
    )


def migrate_past_immediate_broadcast(handler, migrator):
    schedule = AlertSchedule.create_simple_alert(
        handler.domain,
        get_content(handler, handler.events[0], translated=False),
        extra_options=get_extra_scheduling_options(handler, migrator, translated=False),
    )

    broadcast = ImmediateBroadcast.objects.create(
        domain=handler.domain,
        name=handler.nickname,
        last_sent_timestamp=handler.start_datetime,
        schedule=schedule,
        recipients=get_broadcast_recipients(handler),
    )

    return broadcast, schedule


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check",
            default=False,
            help="Check if the migration can proceed but don't make changes",
        )

    def get_rule_migration_function(self, handler):
        if handler.start_condition_type != CASE_CRITERIA:
            return None

        if handler.start_match_type in (MATCH_EXACT, MATCH_REGEX) and not handler.start_value:
            return None

        if handler.start_match_type not in (MATCH_EXACT, MATCH_ANY_VALUE, MATCH_REGEX):
            return None

        if not handler.start_property:
            return None

        if handler.active and handler.uses_parent_case_property:
            return None

        return migrate_rule

    def get_rule_schedule_migration_function(self, handler):
        if handler.start_condition_type != CASE_CRITERIA:
            return None

        if handler.method not in (
            METHOD_SMS,
            METHOD_EMAIL,
            METHOD_SMS_SURVEY,
            METHOD_IVR_SURVEY,
            METHOD_SMS_CALLBACK,
        ):
            return None

        if handler.active and handler.method in (METHOD_IVR_SURVEY, METHOD_SMS_CALLBACK):
            return None

        event_timeout_lengths = [len(event.callback_timeout_intervals) for event in handler.events]

        if (
            handler.method == METHOD_SMS_SURVEY and
            handler.submit_partial_forms and
            not (all(l == 0 for l in event_timeout_lengths) or all(l > 0 for l in event_timeout_lengths))
        ):
            return None

        if handler.include_child_locations:
            return None

        if handler.custom_content_handler and handler.method != METHOD_SMS:
            return None

        if (
            handler.custom_content_handler and
            handler.custom_content_handler not in settings.AVAILABLE_CUSTOM_SCHEDULING_CONTENT
        ):
            if not self.confirm(
                "Custom content id %s not found in the new framework. Migrate anyway? y/n "
                % handler.custom_content_handler
            ):
                return None

        for event in handler.events:
            try:
                if handler.method == METHOD_EMAIL:
                    check_days_until(event.subject)

                if handler.method in (METHOD_SMS, METHOD_EMAIL, METHOD_SMS_CALLBACK):
                    check_days_until(event.message)
            except ValueError:
                return None

        if handler.recipient not in (CUSTOM_RECIPIENTS + (
            RECIPIENT_OWNER,
            RECIPIENT_CASE,
            RECIPIENT_USER_GROUP,
            RECIPIENT_USER,
            RECIPIENT_PARENT_CASE,
            RECIPIENT_SUBCASE,
        )):
            return None

        if handler.recipient == RECIPIENT_SUBCASE and not (
            handler.recipient_case_match_property == '_id' and
            handler.recipient_case_match_type == MATCH_ANY_VALUE
        ):
            return None

        if handler.recipient == RECIPIENT_USER_GROUP and not handler.user_group_id:
            return None

        if handler.user_data_filter and handler.recipient not in (
            RECIPIENT_USER_GROUP,
            RECIPIENT_OWNER,
            RECIPIENT_USER,
            'CASE_OWNER_LOCATION_PARENT',
            'HOST_CASE_OWNER_LOCATION',
            'HOST_CASE_OWNER_LOCATION_PARENT',
        ):
            return None

        fire_time_types = [event.fire_time_type for event in handler.events]
        first_fire_time_type = fire_time_types[0]

        if (
            handler.start_date is None and
            handler.event_interpretation == EVENT_AS_OFFSET and
            handler.start_date is None and
            handler.start_offset == 0 and
            handler.start_day_of_week == DAY_ANY and
            handler.max_iteration_count == 1
        ):
            if (
                len(handler.events) == 1 and
                handler.events[0].day_num == 0 and
                handler.events[0].fire_time in (time(0, 0), time(0, 1))
            ):
                return migrate_simple_alert_schedule
            else:
                return migrate_custom_alert_schedule
        elif (
            handler.event_interpretation == EVENT_AS_SCHEDULE and
            first_fire_time_type in (FIRE_TIME_DEFAULT, FIRE_TIME_CASE_PROPERTY, FIRE_TIME_RANDOM) and
            all(f == first_fire_time_type for f in fire_time_types) and
            not (handler.start_date is None and handler.start_offset < 0)
        ):
            if handler.start_day_of_week != DAY_ANY:
                # Weekly schedule goes here
                if (
                    handler.start_day_of_week >= 0 and
                    handler.start_day_of_week <= 6 and
                    len(handler.events) == 1 and
                    handler.events[0].day_num == 0 and
                    handler.start_offset == 0 and
                    ((handler.schedule_length % 7) == 0 or handler.max_iteration_count == 1)
                ):
                    return migrate_simple_weekly_schedule

                return None
            elif (
                len(handler.events) == 1 and
                handler.events[0].day_num == 0
            ):
                # Simple daily schedule goes here
                return migrate_simple_daily_schedule
            else:
                # Custom daily schedule goes here
                return migrate_custom_daily_schedule
        elif (
            handler.start_date and
            handler.event_interpretation == EVENT_AS_OFFSET and
            handler.start_day_of_week == DAY_ANY
        ):
            if not self.confirm(
                "Does %s.%s reference a date and not a timestamp? " % (handler.case_type, handler.start_date)
            ):
                return None

            repeat_every_override = None
            if handler.max_iteration_count != 1:
                repeat_every_override = self.get_int(
                    "What is the schedule length for %s? (Enter 0 to stop migration)" % handler._id
                )

                if repeat_every_override <= 0:
                    return None

            return get_offset_based_start_date_schedule_migration_function(repeat_every_override)

        return None

    def get_broadcast_migration_function(self, handler):
        if handler.method not in (METHOD_SMS, METHOD_EMAIL, METHOD_SMS_SURVEY):
            return None

        if len(handler.events) != 1:
            return None

        if handler.method in (METHOD_SMS, METHOD_EMAIL) and len(handler.events[0].message) != 1:
            return None

        if handler.method == METHOD_EMAIL and len(handler.events[0].subject) != 1:
            return None

        if handler.recipient not in (
            RECIPIENT_SURVEY_SAMPLE,
            RECIPIENT_USER_GROUP,
            RECIPIENT_LOCATION,
        ):
            return None

        if handler.recipient == RECIPIENT_SURVEY_SAMPLE and not handler.sample_id:
            return None

        if handler.recipient == RECIPIENT_USER_GROUP and not handler.user_group_id:
            return None

        if handler.locked:
            return None

        if handler.start_condition_type != ON_DATETIME:
            return None

        if handler.user_data_filter and handler.recipient not in (
            RECIPIENT_USER_GROUP,
            RECIPIENT_LOCATION,
        ):
            return None

        reminder_result = list(
            CaseReminder.view(
                'reminders/by_domain_handler_case',
                startkey=[handler.domain, handler._id],
                endkey=[handler.domain, handler._id, {}],
                include_docs=True
            ).all()
        )

        if len(reminder_result) > 1:
            return None

        if (
            (len(reminder_result) == 0 or not reminder_result[0].active or reminder_result[0].error) and
            handler.start_datetime and
            handler.start_datetime < datetime.utcnow() and
            handler.event_interpretation == EVENT_AS_OFFSET and
            handler.max_iteration_count == 1 and
            handler.events[0].day_num == 0 and
            handler.events[0].fire_time == time(0, 0)
        ):
            return migrate_past_immediate_broadcast

        return None

    def get_migrator(self, handler):
        if handler.locked:
            return None

        if handler.use_today_if_start_date_is_blank and handler.active and handler.start_date:
            if not self.confirm(
                "Ok to treat use_today_if_start_date_is_blank as False for %s? y/n " % handler._id
            ):
                return None

        if handler.reminder_type == REMINDER_TYPE_DEFAULT:
            for event in handler.events:
                if event.fire_time and event.fire_time.second != 0:
                    return None

            until_references_timestamp = False
            if handler.until:
                until_references_timestamp = self.confirm(
                    "Does until property %s %s.%s reference a timestamp? y/n " %
                    (handler._id, handler.case_type, handler.until)
                )

            rule_migration_function = self.get_rule_migration_function(handler)
            schedule_migration_function = self.get_rule_schedule_migration_function(handler)
            if rule_migration_function and schedule_migration_function:
                return CaseReminderHandlerMigrator(handler, rule_migration_function, schedule_migration_function,
                    until_references_timestamp)

            if self.confirm(
                "A suitable migrator could not be found for %s. Use manual migrator? y/n " % handler._id
            ):
                rule_id = self.get_int("Enter rule id for %s: " % handler._id)
                return ManualCaseReminderHandlerMigrator(handler, rule_id)

            return None
        elif handler.reminder_type == REMINDER_TYPE_ONE_TIME:
            broadcast_migration_function = self.get_broadcast_migration_function(handler)
            if broadcast_migration_function:
                return BroadcastMigrator(handler, broadcast_migration_function)

            return None

    def should_skip(self, handler):
        return handler.reminder_type in (REMINDER_TYPE_KEYWORD_INITIATED, REMINDER_TYPE_SURVEY_MANAGEMENT)

    def migration_already_done(self, domain_obj):
        if project_is_on_new_reminders(domain_obj):
            log("'%s' already uses new reminders, nothing to do" % domain_obj.name)
            return True

        return False

    def ensure_migration_flag_enabled(self, domain):
        while not REMINDERS_MIGRATION_IN_PROGRESS.enabled(domain):
            moves.input("Please enable REMINDERS_MIGRATION_IN_PROGRESS for '%s' and hit enter..." % domain)

        log("REMINDERS_MIGRATION_IN_PROGRESS enabled for %s" % domain)

    def ensure_migration_flag_disabled(self, domain):
        while REMINDERS_MIGRATION_IN_PROGRESS.enabled(domain):
            moves.input("Please disable REMINDERS_MIGRATION_IN_PROGRESS for '%s' and hit enter..." % domain)

        log("REMINDERS_MIGRATION_IN_PROGRESS disabled for %s" % domain)

    def get_handlers_to_migrate(self, domain):
        handlers = CaseReminderHandler.view(
            'reminders/handlers_by_domain_case_type',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True
        ).all()

        return [handler for handler in handlers if not self.should_skip(handler)]

    def get_migrators(self, handlers):
        migrators = []
        cannot_be_migrated = []
        for handler in handlers:
            migrator = self.get_migrator(handler)
            if migrator:
                migrators.append(migrator)
            else:
                cannot_be_migrated.append(handler)

        if cannot_be_migrated:
            log("The following configurations can't be migrated:")
            for handler in cannot_be_migrated:
                log("%s %s" % (handler._id, handler.reminder_type))

        return migrators, cannot_be_migrated

    def migrate_handlers(self, migrators):
        for migrator in migrators:
            migrator.migrate()
            migrator.migrate_schedule_instances()
            migrator.log_migrated_reminder()
            migrator.print_status()

    def confirm(self, message):
        while True:
            answer = moves.input(message).lower()
            if answer == 'y':
                return True
            elif answer == 'n':
                return False

    def get_int(self, message):
        while True:
            answer = moves.input(message)
            try:
                return int(answer)
            except (ValueError, TypeError):
                pass

    def get_locked_count(self, domain):
        return AutomaticUpdateRule.objects.filter(
            domain=domain,
            workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
            deleted=False,
            locked_for_editing=True,
        ).count()

    def refresh_instances(self, domain, migrators):
        log("\n")
        moves.input("Hit enter when ready to refresh instances...")
        log("Refreshing instances...")

        for migrator in migrators:
            migrator.refresh_schedule_instances()

        while self.get_locked_count(domain) > 0:
            sleep(5)

        log("Refresh completed.")

        for migrator in migrators:
            old_target_instance_info = migrator.target_instance_info
            old_target_instance_ids = set(old_target_instance_info)

            migrator.print_status()
            new_target_instance_info = migrator.target_instance_info
            new_target_instance_ids = set(new_target_instance_info)

            created_instance_ids = new_target_instance_ids - old_target_instance_ids
            deleted_instance_ids = old_target_instance_ids - new_target_instance_ids

            differences = False

            log("\nChecking for differences...")
            for instance_id in old_target_instance_ids.intersection(new_target_instance_ids):
                old_info = old_target_instance_info[instance_id]
                new_info = new_target_instance_info[instance_id]
                if old_info != new_info:
                    differences = True
                    log("old: %s" % old_info)
                    log("new: %s" % new_info)

            if created_instance_ids:
                differences = True
                log("\nCreated instances:")
                for instance_id in created_instance_ids:
                    log("new: %s" % new_target_instance_info[instance_id])

            if deleted_instance_ids:
                differences = True
                log("\nDeleted instances:")
                for instance_id in deleted_instance_ids:
                    log("old: %s" % old_target_instance_info[instance_id])

            if not differences:
                log("No differences detected after refresh.")

    def switch_on_new_reminders(self, domain, migrators):
        domain_obj = Domain.get_by_name(domain)
        domain_obj.uses_new_reminders = True
        domain_obj.save()

        for migrator in migrators:
            if migrator.handler.active:
                log("%s is active, deactivating..." % migrator.handler._id)
                migrator.handler.active = False
                migrator.handler.save()
            else:
                log("%s is already inactive" % migrator.handler._id)

        while any([handler.locked for handler in self.get_handlers_to_migrate(domain)]):
            sleep(5)

    def handle(self, domain, **options):
        check_only = options['check']
        log("Handling new reminders migration for %s, --check option is %s" % (domain, check_only))

        domain_obj = Domain.get_by_name(domain)

        if self.migration_already_done(domain_obj):
            return

        if not check_only:
            self.ensure_migration_flag_enabled(domain)

        if not check_only and couch_sql_migration_in_progress(domain):
            log("The Couch to SQL migration is in progress for this project, halting.")
            self.ensure_migration_flag_disabled(domain)
            return

        handlers = self.get_handlers_to_migrate(domain)
        migrators, cannot_be_migrated = self.get_migrators(handlers)
        if cannot_be_migrated:
            return

        log("Migration can proceed")

        if check_only:
            return

        if not self.confirm("Are you sure you want to start the migration? y/n "):
            log("Migrated halted")
            return

        self.migrate_handlers(migrators)
        self.refresh_instances(domain, migrators)

        log("\n")
        if not self.confirm("Ok to switch on new reminders? y/n "):
            log("Migrated halted")
            return

        self.switch_on_new_reminders(domain, migrators)
        self.ensure_migration_flag_disabled(domain)
        log("Migration completed.")
