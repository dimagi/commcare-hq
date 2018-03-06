from __future__ import absolute_import
from celery.task import task
from corehq.messaging.scheduling.models import (
    ImmediateBroadcast,
    ScheduledBroadcast,
    AlertSchedule,
    TimedSchedule,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    delete_alert_schedule_instance,
    delete_timed_schedule_instance,
    get_alert_schedule_instances_for_schedule,
    get_timed_schedule_instances_for_schedule,
    get_alert_schedule_instance,
    save_alert_schedule_instance,
    get_timed_schedule_instance,
    save_timed_schedule_instance,
    get_case_alert_schedule_instances_for_schedule,
    get_case_timed_schedule_instances_for_schedule,
    get_case_schedule_instance,
    save_case_schedule_instance,
    delete_case_schedule_instance,
    delete_alert_schedule_instances_for_schedule,
    delete_timed_schedule_instances_for_schedule,
)
from corehq.util.celery_utils import no_result_task
from datetime import datetime
from dimagi.utils.couch import CriticalSection
from django.conf import settings
import six


class ScheduleInstanceRefresher(object):

    def __init__(self, schedule, new_recipients, existing_instances):
        self.schedule = schedule
        self.new_recipients = set(self._convert_to_tuple_of_tuples(new_recipients))
        self.existing_instances = self._recipient_instance_dict(existing_instances)

        # The model_instance is just an example of any existing instance,
        # or None if none exist yet.
        # When creating instances for new recipients, we should use the
        # model_instance as a starting point so that all recipients
        # receive content at the same point in the schedule.
        self.model_instance = self._get_any_value_or_none(self.existing_instances)

    @staticmethod
    def _get_any_value_or_none(from_dict):
        if from_dict:
            return six.next(six.itervalues(from_dict))

        return None

    @staticmethod
    def _recipient_instance_dict(instances):
        return {
            (instance.recipient_type, instance.recipient_id): instance
            for instance in instances
        }

    @staticmethod
    def _get_reset_case_property_value(case, action_definition):
        # Only allow dynamic case properties here since the formatting of
        # the value is very important if we're comparing from one time to
        # the next
        if action_definition.reset_case_property_name:
            return case.dynamic_case_properties().get(action_definition.reset_case_property_name, '')

        return None

    @staticmethod
    def _convert_to_tuple_of_tuples(list_of_lists):
        list_of_tuples = [tuple(item) for item in list_of_lists]
        return tuple(list_of_tuples)

    def create_new_instance_for_recipient(self, recipient_type, recipient_id):
        """
        Creates the new instance for the recipient, taking self.model_instance
        into account if it exists. The instance is not saved because all instances
        are saved at the end of processing.

        :return: The new instance
        """
        raise NotImplementedError()

    def handle_existing_instance(self, instance):
        """
        Handles any processing needed for an instance that already exists for
        a recipient that we want to keep.
        The instance is not saved in this method because all instances are saved at the
        end of processing.

        :return: True if the instance should be saved at the end of processing,
        otherwise False
        """
        raise NotImplementedError()

    @staticmethod
    def delete_instance(instance):
        if isinstance(instance, AlertScheduleInstance):
            delete_alert_schedule_instance(instance)
        elif isinstance(instance, TimedScheduleInstance):
            delete_timed_schedule_instance(instance)
        elif isinstance(instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance)):
            delete_case_schedule_instance(instance)
        else:
            raise TypeError("Unexpected type: %s" % type(instance))

    @staticmethod
    def save_instance(instance):
        if isinstance(instance, AlertScheduleInstance):
            save_alert_schedule_instance(instance)
        elif isinstance(instance, TimedScheduleInstance):
            save_timed_schedule_instance(instance)
        elif isinstance(instance, (CaseAlertScheduleInstance, CaseTimedScheduleInstance)):
            save_case_schedule_instance(instance)
        else:
            raise TypeError("Unexpected type: %s" % type(instance))

    def refresh(self):
        # A list of (instance, needs_saving) tuples representing the final version
        # of the refreshed instances and whether or not each one needs to be saved
        # at the end of processing. We should avoid saving instances that didn't
        # change to prevent churn on the database tables.
        refreshed_list = []

        for recipient_type_and_id in self.new_recipients:
            recipient_type, recipient_id = recipient_type_and_id

            if recipient_type_and_id not in self.existing_instances:
                refreshed_list.append(
                    (self.create_new_instance_for_recipient(recipient_type, recipient_id), True)
                )

        for recipient_type_and_id, instance in six.iteritems(self.existing_instances):
            if recipient_type_and_id in self.new_recipients:
                needs_saving = self.handle_existing_instance(instance)
                refreshed_list.append((instance, needs_saving))
            else:
                self.delete_instance(instance)

        for instance, needs_saving in refreshed_list:
            if instance.check_active_flag_against_schedule():
                needs_saving = True

            if needs_saving:
                self.save_instance(instance)


class AlertScheduleInstanceRefresher(ScheduleInstanceRefresher):

    def create_new_instance_for_recipient(self, recipient_type, recipient_id):
        if self.model_instance:
            return AlertScheduleInstance.copy_for_recipient(self.model_instance, recipient_type, recipient_id)
        else:
            return AlertScheduleInstance.create_for_recipient(
                self.schedule,
                recipient_type,
                recipient_id,
                move_to_next_event_not_in_the_past=False,
            )

    def handle_existing_instance(self, instance):
        return False


class TimedScheduleInstanceRefresher(ScheduleInstanceRefresher):

    def __init__(self, schedule, new_recipients, existing_instances, start_date=None):
        super(TimedScheduleInstanceRefresher, self).__init__(schedule, new_recipients, existing_instances)
        self.start_date = start_date
        self.schedule_revision = schedule.get_schedule_revision()

    def create_new_instance_for_recipient(self, recipient_type, recipient_id):
        return TimedScheduleInstance.create_for_recipient(
            self.schedule,
            recipient_type,
            recipient_id,
            start_date=self.start_date,
            move_to_next_event_not_in_the_past=True,
            schedule_revision=self.schedule_revision,
        )

    def handle_existing_instance(self, instance):
        if (
            (self.start_date and self.start_date != instance.start_date) or
            (instance.schedule_revision != self.schedule_revision)
        ):
            new_start_date = self.start_date or instance.start_date
            instance.recalculate_schedule(self.schedule, new_start_date=new_start_date)
            return True

        return False


class CaseAlertScheduleInstanceRefresher(ScheduleInstanceRefresher):

    def __init__(self, case, action_definition, rule, schedule, new_recipients, existing_instances):
        super(CaseAlertScheduleInstanceRefresher, self).__init__(schedule, new_recipients, existing_instances)
        self.case = case
        self.action_definition = action_definition
        self.rule = rule
        self.reset_case_property_value = self._get_reset_case_property_value(case, action_definition)

    def create_new_instance_for_recipient(self, recipient_type, recipient_id):
        if self.model_instance:
            instance = CaseAlertScheduleInstance.copy_for_recipient(
                self.model_instance,
                recipient_type,
                recipient_id
            )

            if self.action_definition.reset_case_property_name:
                handle_case_alert_schedule_instance_reset(instance, self.schedule, self.reset_case_property_value)

            return instance
        else:
            return CaseAlertScheduleInstance.create_for_recipient(
                self.schedule,
                recipient_type,
                recipient_id,
                move_to_next_event_not_in_the_past=False,
                case_id=self.case.case_id,
                rule_id=self.rule.pk,
                last_reset_case_property_value=self.reset_case_property_value,
            )

    def handle_existing_instance(self, instance):
        if self.action_definition.reset_case_property_name:
            return handle_case_alert_schedule_instance_reset(
                instance,
                self.schedule,
                self.reset_case_property_value
            )

        return False


class CaseTimedScheduleInstanceRefresher(ScheduleInstanceRefresher):

    def __init__(self, case, action_definition, rule, schedule,
                 new_recipients, existing_instances, start_date=None):
        super(CaseTimedScheduleInstanceRefresher, self).__init__(schedule, new_recipients, existing_instances)
        self.case = case
        self.action_definition = action_definition
        self.rule = rule
        self.reset_case_property_value = self._get_reset_case_property_value(case, action_definition)
        self.start_date = start_date
        self.schedule_revision = schedule.get_schedule_revision(case=case)

    def create_new_instance_for_recipient(self, recipient_type, recipient_id):
        return CaseTimedScheduleInstance.create_for_recipient(
            self.schedule,
            recipient_type,
            recipient_id,
            start_date=self.start_date,
            move_to_next_event_not_in_the_past=True,
            case_id=self.case.case_id,
            rule_id=self.rule.pk,
            last_reset_case_property_value=self.reset_case_property_value,
            schedule_revision=self.schedule_revision,
        )

    def handle_existing_instance(self, instance):
        if self.action_definition.reset_case_property_name:
            if self.reset_case_property_value != instance.last_reset_case_property_value:
                instance.recalculate_schedule(self.schedule)
                instance.last_reset_case_property_value = self.reset_case_property_value
                return True

        if (
            (self.start_date and self.start_date != instance.start_date) or
            (instance.schedule_revision != self.schedule_revision)
        ):
            new_start_date = self.start_date or instance.start_date
            instance.recalculate_schedule(self.schedule, new_start_date=new_start_date)
            return True

        return False


@task(queue=settings.CELERY_REMINDER_RULE_QUEUE, ignore_result=True)
def refresh_alert_schedule_instances(schedule_id, recipients):
    """
    :param schedule_id: the AlertSchedule schedule_id
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    """
    with CriticalSection(['refresh-alert-schedule-instances-for-%s' % schedule_id.hex], timeout=5 * 60):
        schedule = AlertSchedule.objects.get(schedule_id=schedule_id)
        AlertScheduleInstanceRefresher(
            schedule,
            recipients,
            get_alert_schedule_instances_for_schedule(schedule)
        ).refresh()


@task(queue=settings.CELERY_REMINDER_RULE_QUEUE, ignore_result=True)
def refresh_timed_schedule_instances(schedule_id, recipients, start_date=None):
    """
    :param schedule_id: the TimedSchedule schedule_id
    :param start_date: the date to start the TimedSchedule
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    """
    with CriticalSection(['refresh-timed-schedule-instances-for-%s' % schedule_id.hex], timeout=5 * 60):
        schedule = TimedSchedule.objects.get(schedule_id=schedule_id)
        TimedScheduleInstanceRefresher(
            schedule,
            recipients,
            get_timed_schedule_instances_for_schedule(schedule),
            start_date=start_date
        ).refresh()


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_alert_schedule_instances(self, schedule_id):
    """
    :param schedule_id: the AlertSchedule schedule_id
    """
    try:
        with CriticalSection(['refresh-alert-schedule-instances-for-%s' % schedule_id.hex], timeout=30 * 60):
            delete_alert_schedule_instances_for_schedule(AlertScheduleInstance, schedule_id)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_timed_schedule_instances(self, schedule_id):
    """
    :param schedule_id: the TimedSchedule schedule_id
    """
    try:
        with CriticalSection(['refresh-timed-schedule-instances-for-%s' % schedule_id.hex], timeout=30 * 60):
            delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, schedule_id)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_case_alert_schedule_instances(self, schedule_id):
    """
    :param schedule_id: the AlertSchedule schedule_id
    """
    try:
        delete_alert_schedule_instances_for_schedule(CaseAlertScheduleInstance, schedule_id)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_case_timed_schedule_instances(self, schedule_id):
    """
    :param schedule_id: the TimedSchedule schedule_id
    """
    try:
        delete_timed_schedule_instances_for_schedule(CaseTimedScheduleInstance, schedule_id)
    except Exception as e:
        self.retry(exc=e)


def handle_case_alert_schedule_instance_reset(instance, schedule, reset_case_property_value):
    if instance.last_reset_case_property_value != reset_case_property_value:
        instance.reset_schedule(schedule)
        instance.last_reset_case_property_value = reset_case_property_value
        return True

    return False


def refresh_case_alert_schedule_instances(case, schedule, action_definition, rule):
    """
    :param case: the CommCareCase/SQL
    :param schedule: the AlertSchedule
    :param action_definition: the CreateScheduleInstanceActionDefinition that is
    causing the schedule instances to be refreshed
    :param rule: the AutomaticUpdateRule that is causing the schedule instances
    to be refreshed
    """
    CaseAlertScheduleInstanceRefresher(
        case,
        action_definition,
        rule,
        schedule,
        action_definition.recipients,
        get_case_alert_schedule_instances_for_schedule(case.case_id, schedule)
    ).refresh()


def refresh_case_timed_schedule_instances(case, schedule, action_definition, rule, start_date=None):
    """
    :param case: the CommCareCase/SQL
    :param schedule: the TimedSchedule
    :param action_definition: the CreateScheduleInstanceActionDefinition that is
    causing the schedule instances to be refreshed
    :param rule: the AutomaticUpdateRule that is causing the schedule instances
    to be refreshed
    :param start_date: the date to start the TimedSchedule
    """
    CaseTimedScheduleInstanceRefresher(
        case,
        action_definition,
        rule,
        schedule,
        action_definition.recipients,
        get_case_timed_schedule_instances_for_schedule(case.case_id, schedule),
        start_date=start_date
    ).refresh()


def _handle_schedule_instance(instance, save_function):
    """
    :return: True if the event was handled, otherwise False
    """
    if instance.memoized_schedule.deleted:
        instance.delete()
        return False

    if instance.active and instance.next_event_due < datetime.utcnow():
        instance.handle_current_event()
        instance.check_active_flag_against_schedule()
        save_function(instance)
        return True

    return False


def update_broadcast_last_sent_timestamp(broadcast_class, schedule_id):
    broadcast_class.objects.filter(schedule_id=schedule_id).update(last_sent_timestamp=datetime.utcnow())


@no_result_task(queue='reminder_queue')
def handle_alert_schedule_instance(schedule_instance_id):
    with CriticalSection(['handle-alert-schedule-instance-%s' % schedule_instance_id.hex]):
        try:
            instance = get_alert_schedule_instance(schedule_instance_id)
        except AlertScheduleInstance.DoesNotExist:
            return

        if _handle_schedule_instance(instance, save_alert_schedule_instance):
            update_broadcast_last_sent_timestamp(ImmediateBroadcast, instance.alert_schedule_id)


@no_result_task(queue='reminder_queue')
def handle_timed_schedule_instance(schedule_instance_id):
    with CriticalSection(['handle-timed-schedule-instance-%s' % schedule_instance_id.hex]):
        try:
            instance = get_timed_schedule_instance(schedule_instance_id)
        except TimedScheduleInstance.DoesNotExist:
            return

        if _handle_schedule_instance(instance, save_timed_schedule_instance):
            update_broadcast_last_sent_timestamp(ScheduledBroadcast, instance.timed_schedule_id)


@no_result_task(queue='reminder_queue')
def handle_case_alert_schedule_instance(case_id, schedule_instance_id):
    with CriticalSection(['handle-case-alert-schedule-instance-%s' % schedule_instance_id.hex]):
        try:
            instance = get_case_schedule_instance(CaseAlertScheduleInstance, case_id, schedule_instance_id)
        except CaseAlertScheduleInstance.DoesNotExist:
            return

        _handle_schedule_instance(instance, save_case_schedule_instance)


@no_result_task(queue='reminder_queue')
def handle_case_timed_schedule_instance(case_id, schedule_instance_id):
    with CriticalSection(['handle-case-timed-schedule-instance-%s' % schedule_instance_id.hex]):
        try:
            instance = get_case_schedule_instance(CaseTimedScheduleInstance, case_id, schedule_instance_id)
        except CaseTimedScheduleInstance.DoesNotExist:
            return

        _handle_schedule_instance(instance, save_case_schedule_instance)
