from __future__ import absolute_import
import pytz
import uuid
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils import is_commcarecase
from corehq.messaging.scheduling import util
from corehq.messaging.scheduling.exceptions import UnknownRecipientType
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule
from corehq.sql_db.models import PartitionedModel
from corehq.util.timezones.conversions import ServerTime
from corehq.util.timezones.utils import get_timezone_for_domain, coerce_timezone_value
from couchdbkit.exceptions import ResourceNotFound
from datetime import tzinfo
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.modules import to_function
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class ScheduleInstance(PartitionedModel):
    schedule_instance_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    domain = models.CharField(max_length=126)
    recipient_type = models.CharField(max_length=126)
    recipient_id = models.CharField(max_length=126, null=True)
    current_event_num = models.IntegerField()
    schedule_iteration_num = models.IntegerField()
    next_event_due = models.DateTimeField()
    active = models.BooleanField()

    class Meta:
        abstract = True
        index_together = (
            # index for equality comparisons on the leading columns
            ('active', 'next_event_due'),
            ('domain', 'active', 'next_event_due'),
        )

    @property
    def today_for_recipient(self):
        return ServerTime(util.utcnow()).user_time(self.timezone).done().date()

    @property
    @memoized
    def recipient(self):
        if self.recipient_type == 'CommCareCase':
            return CaseAccessors(self.domain).get_case(self.recipient_id)
        elif self.recipient_type == 'CommCareUser':
            return CommCareUser.get(self.recipient_id)
        elif self.recipient_type == 'WebUser':
            return WebUser.get(self.recipient_id)
        elif self.recipient_type == 'CommCareCaseGroup':
            return CommCareCaseGroup.get(self.recipient_id)
        elif self.recipient_type == 'Group':
            return Group.get(self.recipient_id)
        elif self.recipient_type == 'Location':
            return SQLLocation.by_location_id(self.recipient_id)
        else:
            raise UnknownRecipientType(self.recipient_type)

    @property
    @memoized
    def recipient_is_an_individual_contact(self):
        return (
            isinstance(self.recipient, (CommCareUser, WebUser)) or
            is_commcarecase(self.recipient)
        )

    @property
    @memoized
    def timezone(self):
        timezone = None

        if self.recipient_is_an_individual_contact:
            try:
                timezone = self.recipient.get_time_zone()
            except ValidationError:
                pass

        if not timezone:
            timezone = get_timezone_for_domain(self.domain)

        if isinstance(timezone, tzinfo):
            return timezone

        if isinstance(timezone, basestring):
            try:
                return coerce_timezone_value(timezone)
            except ValidationError:
                pass

        return pytz.UTC

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

    def expand_recipients(self):
        """
        Can be used as a generator to iterate over all individual contacts who
        are the recipients of this ScheduleInstance.
        """
        if self.recipient is None:
            return
        elif self.recipient_is_an_individual_contact:
            yield self.recipient
        elif isinstance(self.recipient, CommCareCaseGroup):
            case_group = self.recipient
            for case in case_group.get_cases():
                yield case
        elif isinstance(self.recipient, Group):
            group = self.recipient
            for user in group.get_users(is_active=True, only_commcare=False):
                yield user
        elif isinstance(self.recipient, SQLLocation):
            location = self.recipient
            if self.memoized_schedule.include_descendant_locations:
                location_ids = location.get_descendants(include_self=True).filter(is_archived=False).location_ids()
            else:
                location_ids = [location.location_id]

            user_ids = set()
            for location_id in location_ids:
                for user in get_all_users_by_location(self.domain, location_id):
                    if user.is_active and user.get_id not in user_ids:
                        user_ids.add(user.get_id)
                        yield user
        else:
            raise UnknownRecipientType(self.recipient.__class__.__name__)

    def handle_current_event(self):
        content = self.memoized_schedule.get_current_event_content(self)
        for recipient in self.expand_recipients():
            content.send(recipient, self)
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
        self.schedule_revision = schedule.memoized_schedule_revision


class AlertScheduleInstance(AbstractAlertScheduleInstance):
    partition_attr = 'schedule_instance_id'

    class Meta(AbstractAlertScheduleInstance.Meta):
        db_table = 'scheduling_alertscheduleinstance'


class TimedScheduleInstance(AbstractTimedScheduleInstance):
    partition_attr = 'schedule_instance_id'

    class Meta(AbstractTimedScheduleInstance.Meta):
        db_table = 'scheduling_timedscheduleinstance'


class CaseScheduleInstanceMixin(object):

    @property
    @memoized
    def case(self):
        try:
            return CaseAccessors(self.domain).get_case(self.case_id)
        except (CaseNotFound, ResourceNotFound):
            return None

    @property
    @memoized
    def case_owner(self):
        if self.case:
            return get_wrapped_owner(get_owner_id(self.case))

        return None

    @property
    @memoized
    def recipient(self):
        if self.recipient_type == 'Self':
            return self.case
        elif self.recipient_type == 'Owner':
            return self.case_owner
        if self.recipient_type == 'LastSubmittingUser':
            return None
        elif self.recipient_type == 'ParentCase':
            return None
        elif self.recipient_type == 'SubCase':
            return None
        elif self.recipient_type == 'CustomRecipient':
            custom_function = to_function(
                settings.AVAILABLE_CUSTOM_SCHEDULING_RECIPIENTS[self.recipient_id][0]
            )
            return custom_function(self)
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
        index_together = AbstractAlertScheduleInstance.Meta.index_together + (
            ('case_id', 'alert_schedule_id'),
        )
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
        index_together = AbstractTimedScheduleInstance.Meta.index_together + (
            ('case_id', 'timed_schedule_id'),
        )
        unique_together = (
            ('case_id', 'timed_schedule_id', 'recipient_type', 'recipient_id'),
        )
