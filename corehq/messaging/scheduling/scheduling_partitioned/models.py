import attr
import pytz
import sys
import uuid
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CommCareUser, WebUser, CouchUser
from corehq.apps.users.util import format_username
from corehq.form_processor.models import DEFAULT_PARENT_IDENTIFIER
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling import util
from corehq.messaging.scheduling.exceptions import UnknownRecipientType
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule, IVRSurveyContent, SMSCallbackContent
from corehq.sql_db.models import PartitionedModel
from corehq.util.timezones.conversions import ServerTime, UserTime
from corehq.util.timezones.utils import get_timezone_for_domain, coerce_timezone_value
from couchdbkit.exceptions import ResourceNotFound
from datetime import timedelta, date, datetime, time
from memoized import memoized
from dimagi.utils.couch import get_redis_lock
from dimagi.utils.modules import to_function
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


# The number of minutes after which a schedule instance is considered stale.
# Stale instances are just fast-forwarded according to their schedule and
# no content is sent.
STALE_SCHEDULE_INSTANCE_INTERVAL = 2 * 24 * 60


class ScheduleInstance(PartitionedModel):
    schedule_instance_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126)
    recipient_type = models.CharField(max_length=126)
    recipient_id = models.CharField(max_length=126, null=True)
    current_event_num = models.IntegerField()
    schedule_iteration_num = models.IntegerField()
    next_event_due = models.DateTimeField()
    active = models.BooleanField()
    attempts = models.IntegerField(default=0)
    last_atempt = models.DateTimeField(null=True)

    RECIPIENT_TYPE_CASE = 'CommCareCase'
    RECIPIENT_TYPE_MOBILE_WORKER = 'CommCareUser'
    RECIPIENT_TYPE_WEB_USER = 'WebUser'
    RECIPIENT_TYPE_CASE_GROUP = 'CommCareCaseGroup'
    RECIPIENT_TYPE_USER_GROUP = 'Group'
    RECIPIENT_TYPE_LOCATION = 'Location'

    class Meta(object):
        abstract = True
        index_together = (
            # index for equality comparisons on the leading columns
            ('active', 'next_event_due'),
            ('domain', 'active', 'next_event_due'),
        )

    def get_today_for_recipient(self, schedule):
        return ServerTime(util.utcnow()).user_time(self.get_timezone(schedule)).done().date()

    @property
    @memoized
    def recipient(self):
        if self.recipient_type == self.RECIPIENT_TYPE_CASE:
            try:
                case = CommCareCase.objects.get_case(self.recipient_id, self.domain)
            except CaseNotFound:
                return None

            if case.domain != self.domain:
                return None

            return case
        elif self.recipient_type == self.RECIPIENT_TYPE_MOBILE_WORKER:
            user = CouchUser.get_by_user_id(self.recipient_id, domain=self.domain)
            if not isinstance(user, CommCareUser):
                return None

            return user
        elif self.recipient_type == self.RECIPIENT_TYPE_WEB_USER:
            user = CouchUser.get_by_user_id(self.recipient_id, domain=self.domain)
            if not isinstance(user, WebUser):
                return None

            return user
        elif self.recipient_type == self.RECIPIENT_TYPE_CASE_GROUP:
            try:
                group = CommCareCaseGroup.get(self.recipient_id)
            except ResourceNotFound:
                return None

            if group.domain != self.domain:
                return None

            return group
        elif self.recipient_type == self.RECIPIENT_TYPE_USER_GROUP:
            try:
                group = Group.get(self.recipient_id)
            except ResourceNotFound:
                return None

            if group.domain != self.domain:
                return None

            return group
        elif self.recipient_type == self.RECIPIENT_TYPE_LOCATION:
            location = SQLLocation.by_location_id(self.recipient_id)

            if location is None:
                return None

            if location.domain != self.domain:
                return None

            return location
        else:
            raise UnknownRecipientType(self.recipient_type)

    @staticmethod
    def recipient_is_an_individual_contact(recipient):
        return (
            isinstance(recipient, (CommCareUser, WebUser))
            or is_commcarecase(recipient)
            or isinstance(recipient, EmailAddressRecipient)
        )

    @property
    @memoized
    def domain_timezone(self):
        try:
            return get_timezone_for_domain(self.domain)
        except ValidationError:
            return pytz.UTC

    def get_timezone(self, schedule):
        if self.recipient_is_an_individual_contact(self.recipient):
            try:
                timezone_str = self.recipient.get_time_zone()
                if timezone_str:
                    return coerce_timezone_value(timezone_str)
            except ValidationError:
                pass

        if schedule.use_utc_as_default_timezone:
            # See note on Schedule.use_utc_as_default_timezone.
            # When use_utc_as_default_timezone is enabled and the contact has
            # no time zone configured, use UTC.
            return pytz.UTC
        else:
            return self.domain_timezone

    @classmethod
    def create_for_recipient(cls, schedule, recipient_type, recipient_id, start_date=None,
            move_to_next_event_not_in_the_past=True, **additional_fields):

        obj = cls(
            domain=schedule.domain,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            current_event_num=0,
            schedule_iteration_num=1,
            active=True,
            **additional_fields
        )

        obj.schedule = schedule
        schedule.set_first_event_due_timestamp(obj, start_date)

        if move_to_next_event_not_in_the_past:
            schedule.move_to_next_event_not_in_the_past(obj)

        return obj

    @staticmethod
    def expand_group(group):
        if not isinstance(group, Group):
            raise TypeError("Expected Group")

        for user in group.get_users(is_active=True, only_commcare=False):
            yield user

    @staticmethod
    def expand_location_ids(domain, location_ids):
        user_ids = set()
        for location_id in location_ids:
            for user in get_all_users_by_location(domain, location_id):
                if user.is_active and user.get_id not in user_ids:
                    user_ids.add(user.get_id)
                    yield user

    def _expand_recipient(self, recipient):
        if recipient is None:
            return
        elif self.recipient_is_an_individual_contact(recipient):
            yield recipient
        elif isinstance(recipient, CommCareCaseGroup):
            case_group = recipient
            for case in case_group.get_cases():
                yield case
        elif isinstance(recipient, Group):
            for user in self.expand_group(recipient):
                yield user
        elif isinstance(recipient, SQLLocation):
            location = recipient
            if (
                self.recipient_type == self.RECIPIENT_TYPE_LOCATION
                and self.memoized_schedule.include_descendant_locations
            ):
                # Only include descendant locations when the recipient_type
                # is RECIPIENT_TYPE_LOCATION. This is because we only do this
                # for locations the user selected in the UI, and not for
                # locations that happen to get here because they are a case
                # owner, for example.
                qs = location.get_descendants(include_self=True).filter(is_archived=False)

                # We also only apply the location_type_filter when the recipient_type
                # is RECIPIENT_TYPE_LOCATION for the same reason.
                if self.memoized_schedule.location_type_filter:
                    qs = qs.filter(location_type_id__in=self.memoized_schedule.location_type_filter)

                location_ids = qs.location_ids()
            else:
                location_ids = [location.location_id]

            for user in self.expand_location_ids(self.domain, location_ids):
                yield user
        else:
            raise UnknownRecipientType(recipient.__class__.__name__)

    def convert_to_set(self, value):
        if isinstance(value, (list, tuple)):
            return set(value)

        return set([value])

    def passes_user_data_filter(self, contact):
        if not isinstance(contact, CouchUser):
            return True

        if not self.memoized_schedule.user_data_filter:
            return True

        user_data = contact.get_user_data(self.domain)
        for key, value in self.memoized_schedule.user_data_filter.items():
            if key not in user_data:
                return False

            allowed_values_set = self.convert_to_set(value)
            actual_values_set = self.convert_to_set(user_data[key])

            if actual_values_set.isdisjoint(allowed_values_set):
                return False

        return True

    def expand_recipients(self):
        """
        Can be used as a generator to iterate over all individual contacts who
        are the recipients of this ScheduleInstance.
        """
        recipient_list = self.recipient
        if not isinstance(recipient_list, list):
            recipient_list = [recipient_list]

        for member in recipient_list:
            for contact in self._expand_recipient(member):
                if self.passes_user_data_filter(contact):
                    yield contact

    def get_content_send_lock(self, recipient):
        if is_commcarecase(recipient):
            doc_type = 'CommCareCase'
            doc_id = recipient.case_id
        else:
            doc_type = recipient.doc_type
            doc_id = recipient.get_id

        key = "send-content-for-%s-%s-%s-%s-%s" % (
            self.__class__.__name__,
            self.schedule_instance_id.hex,
            self.next_event_due.strftime('%Y-%m-%d %H:%M:%S'),
            doc_type,
            doc_id,
        )
        return get_redis_lock(
            key,
            timeout=STALE_SCHEDULE_INSTANCE_INTERVAL * 60,
            name="send_content_for_%s" % type(self).__name__,
            track_unreleased=False,
        )

    def send_current_event_content_to_recipients(self):
        content = self.memoized_schedule.get_current_event_content(self)

        if isinstance(content, (IVRSurveyContent, SMSCallbackContent)):
            raise TypeError(
                "IVR and Callback use cases are no longer supported. "
                "How did this schedule instance end up as active?"
            )

        if isinstance(self, CaseScheduleInstanceMixin):
            content.set_context(case=self.case, schedule_instance=self)
        else:
            content.set_context(schedule_instance=self)

        logged_event = MessagingEvent.create_from_schedule_instance(self, content)

        recipient_count = 0
        for recipient in self.expand_recipients():
            recipient_count += 1

            #   The framework will retry sending a non-processed schedule instance
            # once every hour.

            #   If we are processing a long list of recipients here and an error
            # occurs half-way through, we don't want to reprocess the entire list
            # of recipients again when the framework retries it an hour later.

            #   So we use a non-blocking lock tied to the event due time and recipient
            # to make sure that we don't try resending the same content to the same
            # recipient more than once in the event of a retry.

            #   If we succeed in sending the content, we don't release the lock so
            # that it won't retry later. If we fail in sending the content, we release
            # the lock so that it will retry later.

            lock = self.get_content_send_lock(recipient)
            if lock.acquire(blocking=False):
                try:
                    content.send(recipient, logged_event)
                except:  # noqa: E722
                    error = sys.exc_info()[1]
                    # Release the lock if an error happened so that we can try sending
                    # to this recipient again later.
                    lock.release()
                    logged_event.error(
                        MessagingEvent.ERROR_INTERNAL_SERVER_ERROR,
                        additional_error_text=str(error),
                    )
                    raise

        # Update the MessagingEvent for reporting
        if recipient_count == 0:
            logged_event.error(MessagingEvent.ERROR_NO_RECIPIENT)
        else:
            logged_event.completed()

    @property
    def is_stale(self):
        return (util.utcnow() - self.next_event_due) > timedelta(minutes=STALE_SCHEDULE_INSTANCE_INTERVAL)

    def handle_current_event(self):
        if not self.is_stale:
            self.send_current_event_content_to_recipients()

        # As a precaution, always explicitly move to the next event after processing the current
        # event to prevent ever getting stuck on the current event.
        self.memoized_schedule.move_to_next_event(self)
        self.memoized_schedule.move_to_next_event_not_in_the_past(self)

    @property
    def schedule(self):
        raise NotImplementedError()

    @schedule.setter
    def schedule(self, value):
        raise NotImplementedError()

    @property
    @memoized
    def memoized_schedule(self):
        """
        This is named with a memoized_ prefix to be clear that it should only be used
        when the schedule is not changing.
        """
        return self.schedule

    def additional_deactivation_condition_reached(self):
        """
        Subclasses can override this to provide additional checks under
        which a ScheduleInstance should be deactivated, which will be checked
        when the ScheduleInstances are being refreshed as well as right before
        and after processing them, through check_active_flag_against_schedule().
        """
        return False

    def should_be_active(self):
        return self.memoized_schedule.active and not self.additional_deactivation_condition_reached()

    def check_active_flag_against_schedule(self):
        """
        Returns True if the active flag was changed and the schedule instance should be saved.
        Returns False if nothing changed.
        """
        should_be_active = self.should_be_active()

        if self.active and not should_be_active:
            self.active = False
            return True

        if not self.active and should_be_active:
            if self.memoized_schedule.total_iterations_complete(self):
                return False

            self.active = True
            self.memoized_schedule.move_to_next_event_not_in_the_past(self)
            return True

        return False


class AbstractAlertScheduleInstance(ScheduleInstance):
    alert_schedule_id = models.UUIDField()

    class Meta(ScheduleInstance.Meta):
        abstract = True

    @property
    def schedule(self):
        return AlertSchedule.objects.get(schedule_id=self.alert_schedule_id)

    @schedule.setter
    def schedule(self, value):
        if not isinstance(value, AlertSchedule):
            raise ValueError("Expected an instance of AlertSchedule")

        self.alert_schedule_id = value.schedule_id

    @staticmethod
    def copy_for_recipient(instance, recipient_type, recipient_id):
        """
        We can copy alert schedule instances for any recipient because the
        recipient's time zone doesn't factor into the calculation of the
        next event due timestamp as it does for timed schedule instances.
        """
        if not isinstance(instance, AbstractAlertScheduleInstance):
            raise TypeError("Expected an alert schedule instance")

        new_instance = type(instance)()

        for field in instance._meta.fields:
            if field.name not in ['schedule_instance_id', 'recipient_type', 'recipient_id']:
                setattr(new_instance, field.name, getattr(instance, field.name))

        new_instance.recipient_type = recipient_type
        new_instance.recipient_id = recipient_id

        return new_instance

    def reset_schedule(self, schedule=None):
        """
        Resets this alert schedule instance and puts it into a state which
        is the same as if it had just spawned now.
        """
        schedule = schedule or self.memoized_schedule
        self.current_event_num = 0
        self.schedule_iteration_num = 1
        self.active = True
        schedule.set_first_event_due_timestamp(self)


class AbstractTimedScheduleInstance(ScheduleInstance):
    timed_schedule_id = models.UUIDField()
    start_date = models.DateField()
    schedule_revision = models.CharField(max_length=126, null=True)

    class Meta(ScheduleInstance.Meta):
        abstract = True

    @property
    def schedule(self):
        return TimedSchedule.objects.get(schedule_id=self.timed_schedule_id)

    @schedule.setter
    def schedule(self, value):
        if not isinstance(value, TimedSchedule):
            raise ValueError("Expected an instance of TimedSchedule")

        self.timed_schedule_id = value.schedule_id

    def recalculate_schedule(self, schedule=None, new_start_date=None):
        """
        Resets the start_date and recalulates the next_event_due timestamp for
        this AbstractTimedScheduleInstance.

        :param schedule: The TimedSchedule to use to avoid a lookup; if None,
        self.memoized_schedule is used
        :param new_start_date: The start date to use when recalculating the schedule;
        If None, the current date is used
        """
        schedule = schedule or self.memoized_schedule
        self.current_event_num = 0
        self.schedule_iteration_num = 1
        self.active = True
        schedule.set_first_event_due_timestamp(self, start_date=new_start_date)
        schedule.move_to_next_event_not_in_the_past(self)
        self.schedule_revision = schedule.get_schedule_revision(case=schedule.get_case_or_none(self))


class AlertScheduleInstance(AbstractAlertScheduleInstance):
    partition_attr = 'schedule_instance_id'

    class Meta(AbstractAlertScheduleInstance.Meta):
        db_table = 'scheduling_alertscheduleinstance'

        unique_together = (
            ('alert_schedule_id', 'recipient_type', 'recipient_id'),
        )


class TimedScheduleInstance(AbstractTimedScheduleInstance):
    partition_attr = 'schedule_instance_id'

    class Meta(AbstractTimedScheduleInstance.Meta):
        db_table = 'scheduling_timedscheduleinstance'

        unique_together = (
            ('timed_schedule_id', 'recipient_type', 'recipient_id'),
        )


@attr.s
class EmailAddressRecipient(object):
    case = attr.ib()
    email_property = attr.ib()

    @property
    def doc_type(self):
        return None

    @property
    def get_id(self):
        return self.get_email()

    def get_email(self):
        return self.case.get_case_property(self.email_property)

    def get_language_code(self):
        return self.case.get_language_code()

    def get_time_zone(self):
        return self.case.get_time_zone()


class CaseScheduleInstanceMixin(object):

    RECIPIENT_TYPE_SELF = 'Self'
    RECIPIENT_TYPE_CASE_OWNER = 'Owner'
    RECIPIENT_TYPE_LAST_SUBMITTING_USER = 'LastSubmittingUser'
    RECIPIENT_TYPE_PARENT_CASE = 'ParentCase'
    RECIPIENT_TYPE_ALL_CHILD_CASES = 'AllChildCases'
    RECIPIENT_TYPE_CUSTOM = 'CustomRecipient'
    RECIPIENT_TYPE_CASE_PROPERTY_USER = 'CasePropertyUser'
    RECIPIENT_TYPE_CASE_PROPERTY_EMAIL = 'CasePropertyEmail'

    @property
    @memoized
    def case(self):
        try:
            return CommCareCase.objects.get_case(self.case_id, self.domain)
        except CaseNotFound:
            return None

    @property
    @memoized
    def case_owner(self):
        if self.case:
            return get_wrapped_owner(get_owner_id(self.case))

        return None

    def additional_deactivation_condition_reached(self):
        from corehq.apps.data_interfaces.models import _try_date_conversion

        if self.memoized_schedule.stop_date_case_property_name and self.case:
            values = self.case.resolve_case_property(self.memoized_schedule.stop_date_case_property_name)
            values = [element.value for element in values]

            timezone = pytz.UTC if self.memoized_schedule.use_utc_as_default_timezone else self.domain_timezone

            for stop_date in values:
                if isinstance(stop_date, datetime):
                    pass
                elif isinstance(stop_date, date):
                    stop_date = datetime.combine(stop_date, time(0, 0))
                else:
                    stop_date = _try_date_conversion(stop_date)

                if not isinstance(stop_date, datetime):
                    continue

                if stop_date.tzinfo:
                    stop_date = stop_date.astimezone(pytz.UTC).replace(tzinfo=None)
                else:
                    stop_date = UserTime(stop_date, timezone).server_time().done()

                if self.next_event_due >= stop_date:
                    return True

        return False

    @property
    @memoized
    def recipient(self):
        if self.recipient_type == self.RECIPIENT_TYPE_SELF:
            return self.case
        elif self.recipient_type == self.RECIPIENT_TYPE_CASE_OWNER:
            return self.case_owner
        elif self.recipient_type == self.RECIPIENT_TYPE_LAST_SUBMITTING_USER:
            if self.case and self.case.modified_by:
                return CouchUser.get_by_user_id(self.case.modified_by, domain=self.domain)

            return None
        elif self.recipient_type == self.RECIPIENT_TYPE_PARENT_CASE:
            if self.case:
                return self.case.parent

            return None
        elif self.recipient_type == self.RECIPIENT_TYPE_ALL_CHILD_CASES:
            if self.case:
                return list(self.case.get_subcases(index_identifier=DEFAULT_PARENT_IDENTIFIER))

            return None
        elif self.recipient_type == self.RECIPIENT_TYPE_CUSTOM:
            custom_function = to_function(
                settings.AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS[self.recipient_id][0]
            )
            return custom_function(self)
        elif self.recipient_type == self.RECIPIENT_TYPE_CASE_PROPERTY_USER:
            username = self.case.get_case_property(self.recipient_id)
            full_username = format_username(username, self.domain)
            return CommCareUser.get_by_username(full_username)
        elif self.recipient_type == self.RECIPIENT_TYPE_CASE_PROPERTY_EMAIL:
            return EmailAddressRecipient(self.case, self.recipient_id)
        else:
            return super(CaseScheduleInstanceMixin, self).recipient


class CaseAlertScheduleInstance(CaseScheduleInstanceMixin, AbstractAlertScheduleInstance):
    # Points to the CommCareCase/SQL that spawned this schedule instance
    partition_attr = 'case_id'
    case_id = models.CharField(max_length=255)

    # Points to the AutomaticUpdateRule that spawned this schedule instance
    rule_id = models.IntegerField()

    # See corehq.apps.data_interfaces.models.CreateScheduleInstanceActionDefinition.reset_case_property_name
    last_reset_case_property_value = models.TextField(null=True)

    class Meta(AbstractAlertScheduleInstance.Meta):
        db_table = 'scheduling_casealertscheduleinstance'
        index_together = AbstractAlertScheduleInstance.Meta.index_together
        unique_together = (
            ('case_id', 'alert_schedule_id', 'recipient_type', 'recipient_id'),
        )


class CaseTimedScheduleInstance(CaseScheduleInstanceMixin, AbstractTimedScheduleInstance):
    # Points to the CommCareCase/SQL that spawned this schedule instance
    partition_attr = 'case_id'
    case_id = models.CharField(max_length=255)

    # Points to the AutomaticUpdateRule that spawned this schedule instance
    rule_id = models.IntegerField()

    # See corehq.apps.data_interfaces.models.CreateScheduleInstanceActionDefinition.reset_case_property_name
    last_reset_case_property_value = models.TextField(null=True)

    class Meta(AbstractTimedScheduleInstance.Meta):
        db_table = 'scheduling_casetimedscheduleinstance'
        index_together = AbstractTimedScheduleInstance.Meta.index_together
        unique_together = (
            ('case_id', 'timed_schedule_id', 'recipient_type', 'recipient_id'),
        )

    def additional_deactivation_condition_reached(self):
        from corehq.messaging.tasks import get_cached_rule
        additional_deactivation_condition_reached = super().additional_deactivation_condition_reached()
        rule = get_cached_rule(self.case.domain, self.rule_id)
        if not rule:
            return additional_deactivation_condition_reached

        criteria_match = rule.criteria_match(self.case, datetime.utcnow())
        return additional_deactivation_condition_reached and criteria_match
