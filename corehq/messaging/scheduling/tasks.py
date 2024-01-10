import uuid
from datetime import datetime, timedelta

from django.conf import settings

from bs4 import BeautifulSoup
from celery.schedules import crontab

from dimagi.utils.couch import CriticalSection

from corehq.apps.celery import task
from corehq.apps.celery.periodic import periodic_task
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    ImmediateBroadcast,
    ScheduledBroadcast,
    TimedSchedule,
)
from corehq.messaging.scheduling.models.content import EmailContent, EmailImage
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    delete_alert_schedule_instance,
    delete_alert_schedule_instances_for_schedule,
    delete_case_schedule_instance,
    delete_schedule_instances_by_case_id,
    delete_timed_schedule_instance,
    delete_timed_schedule_instances_for_schedule,
    get_alert_schedule_instance,
    get_alert_schedule_instances_for_schedule,
    get_case_alert_schedule_instances_for_schedule,
    get_case_schedule_instance,
    get_case_timed_schedule_instances_for_schedule,
    get_timed_schedule_instance,
    get_timed_schedule_instances_for_schedule,
    save_alert_schedule_instance,
    save_case_schedule_instance,
    save_timed_schedule_instance,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    CaseAlertScheduleInstance,
    CaseScheduleInstanceMixin,
    CaseTimedScheduleInstance,
    TimedScheduleInstance,
)
from corehq.util.celery_utils import no_result_task
from corehq.util.dates import iso_string_to_date


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
            return next(iter(from_dict.values()))

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

        for recipient_type_and_id, instance in self.existing_instances.items():
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
            (self.start_date and self.start_date != instance.start_date)
            or (instance.schedule_revision != self.schedule_revision)
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
            self.handle_existing_instance(instance)
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
        start_date = self.start_date
        if not start_date and self.model_instance:
            start_date = self.model_instance.start_date

        return CaseTimedScheduleInstance.create_for_recipient(
            self.schedule,
            recipient_type,
            recipient_id,
            start_date=start_date,
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
            (self.start_date and self.start_date != instance.start_date)
            or (instance.schedule_revision != self.schedule_revision)
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
    schedule_uuid = uuid.UUID(schedule_id)
    with CriticalSection(['refresh-alert-schedule-instances-for-%s' % schedule_uuid.hex], timeout=5 * 60):
        schedule = AlertSchedule.objects.get(schedule_id=schedule_uuid)
        AlertScheduleInstanceRefresher(
            schedule,
            recipients,
            get_alert_schedule_instances_for_schedule(schedule)
        ).refresh()


@task(queue=settings.CELERY_REMINDER_RULE_QUEUE, ignore_result=True)
def refresh_timed_schedule_instances(schedule_id, recipients, start_date_iso_string=None):
    """
    :param schedule_id: type str that is hex representation of the TimedSchedule schedule_id (UUID)
    :param recipients: a list of (recipient_type, recipient_id) tuples; the
    recipient type should be one of the values checked in ScheduleInstance.recipient
    :param start_date_iso_string: the date to start the TimedSchedule formatted as an iso string
    """
    schedule_uuid = uuid.UUID(schedule_id)
    start_date = iso_string_to_date(start_date_iso_string) if start_date_iso_string else None
    with CriticalSection(['refresh-timed-schedule-instances-for-%s' % schedule_uuid.hex], timeout=5 * 60):
        schedule = TimedSchedule.objects.get(schedule_id=schedule_uuid)
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
    :param schedule_id: type str that is hex representation of the AlertSchedule schedule_id (UUID)
    """
    schedule_uuid = uuid.UUID(schedule_id)
    try:
        with CriticalSection(['refresh-alert-schedule-instances-for-%s' % schedule_uuid.hex], timeout=30 * 60):
            delete_alert_schedule_instances_for_schedule(AlertScheduleInstance, schedule_uuid)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_timed_schedule_instances(self, schedule_id):
    """
    :param schedule_id: type str that is hex representation of the TimedSchedule schedule_id (UUID)
    """
    schedule_uuid = uuid.UUID(schedule_id)
    try:
        with CriticalSection(['refresh-timed-schedule-instances-for-%s' % schedule_uuid.hex], timeout=30 * 60):
            delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, schedule_uuid)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_case_alert_schedule_instances(self, schedule_id):
    """
    :param schedule_id: type str that is hex representation of the AlertSchedule schedule_id (UUID)
    """
    schedule_uuid = uuid.UUID(schedule_id)
    try:
        delete_alert_schedule_instances_for_schedule(CaseAlertScheduleInstance, schedule_uuid)
    except Exception as e:
        self.retry(exc=e)


@no_result_task(queue=settings.CELERY_REMINDER_RULE_QUEUE, acks_late=True,
                default_retry_delay=60 * 60, max_retries=24, bind=True)
def delete_case_timed_schedule_instances(self, schedule_id):
    """
    :param schedule_id: type str that is hex representation of the TimedSchedule schedule_id (UUID)
    """
    schedule_uuid = uuid.UUID(schedule_id)
    try:
        delete_timed_schedule_instances_for_schedule(CaseTimedScheduleInstance, schedule_uuid)
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
    if (
        instance.memoized_schedule.deleted
        or (
            isinstance(instance, CaseScheduleInstanceMixin)
            and (instance.case is None or instance.case.is_deleted)
        )
    ):
        instance.delete()
        return False

    if instance.active and instance.next_event_due < datetime.utcnow():
        # We have to call check_active_flag_against_schedule before processing
        # in case the schedule was deactivated and the task which deactivates
        # instances hasn't finished yet. We also have to call it after processing
        # to handle the other checks whose result might change based on next_event_due
        # changing.
        instance.check_active_flag_against_schedule()
        if not instance.active:
            # The instance was just deactivated
            save_function(instance)
            return False

        try:
            instance.handle_current_event()
        except Exception:
            instance.attempts += 1
            instance.last_attempt = datetime.utcnow()
            instance.next_event_due += timedelta(hours=instance.attempts)
            save_function(instance)
            raise
        instance.check_active_flag_against_schedule()
        save_function(instance)
        return True

    return False


def update_broadcast_last_sent_timestamp(broadcast_class, schedule_id):
    broadcast_class.objects.filter(schedule_id=schedule_id).update(last_sent_timestamp=datetime.utcnow())


@no_result_task(queue='reminder_queue')
def handle_alert_schedule_instance(schedule_instance_id, domain):
    schedule_instance_uuid = uuid.UUID(schedule_instance_id)
    with CriticalSection(['handle-alert-schedule-instance-%s' % schedule_instance_uuid.hex]):
        try:
            instance = get_alert_schedule_instance(schedule_instance_uuid)
        except AlertScheduleInstance.DoesNotExist:
            return

        if _handle_schedule_instance(instance, save_alert_schedule_instance):
            update_broadcast_last_sent_timestamp(ImmediateBroadcast, instance.alert_schedule_id)


@no_result_task(queue='reminder_queue')
def handle_timed_schedule_instance(schedule_instance_id, domain):
    schedule_instance_uuid = uuid.UUID(schedule_instance_id)
    with CriticalSection(['handle-timed-schedule-instance-%s' % schedule_instance_uuid.hex]):
        try:
            instance = get_timed_schedule_instance(schedule_instance_uuid)
        except TimedScheduleInstance.DoesNotExist:
            return

        if _handle_schedule_instance(instance, save_timed_schedule_instance):
            update_broadcast_last_sent_timestamp(ScheduledBroadcast, instance.timed_schedule_id)


@no_result_task(queue='reminder_queue')
def handle_case_alert_schedule_instance(case_id, schedule_instance_id, domain):
    schedule_instance_uuid = uuid.UUID(schedule_instance_id)
    # Use the same lock key as the tasks which refresh case schedule instances
    from corehq.messaging.tasks import get_sync_key
    with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
        try:
            instance = get_case_schedule_instance(CaseAlertScheduleInstance, case_id, schedule_instance_uuid)
        except CaseAlertScheduleInstance.DoesNotExist:
            return

        _handle_schedule_instance(instance, save_case_schedule_instance)


@no_result_task(queue='reminder_queue')
def handle_case_timed_schedule_instance(case_id, schedule_instance_id, domain):
    schedule_instance_uuid = uuid.UUID(schedule_instance_id)
    # Use the same lock key as the tasks which refresh case schedule instances
    from corehq.messaging.tasks import get_sync_key
    with CriticalSection([get_sync_key(case_id)], timeout=5 * 60):
        try:
            instance = get_case_schedule_instance(CaseTimedScheduleInstance, case_id, schedule_instance_uuid)
        except CaseTimedScheduleInstance.DoesNotExist:
            return

        _handle_schedule_instance(instance, save_case_schedule_instance)


@no_result_task(queue='background_queue', acks_late=True)
def delete_schedule_instances_for_cases(domain, case_ids):
    for case_id in case_ids:
        delete_schedule_instances_by_case_id(domain, case_id)


@periodic_task(run_every=crontab(minute='0', hour='1'), queue=settings.CELERY_PERIODIC_QUEUE)
def delete_unused_messaging_images():
    """Removes images that were uploaded to be used in emails, but were then deleted for whatever reason

    """
    image_ids = set(EmailImage.get_all_blob_ids())

    present_image_ids = set()
    # There is no easy way of figuring out the domain from EmailContent
    # directly, so we only fetch those EmailContents that have html.
    email_messages = EmailContent.objects.values_list("html_message", flat=True).filter(html_message__isnull=False)
    for messages in email_messages:
        for lang, content in messages.items():
            soup = BeautifulSoup(content, features='lxml')
            images = soup.find_all("img")
            for image in images:
                try:
                    present_image_ids.add(image['src'].split('/')[-1])
                except KeyError:
                    continue

    unused_images = image_ids - present_image_ids
    EmailImage.bulk_delete(unused_images)
