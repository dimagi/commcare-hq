from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.conf import settings

REMINDER__REMINDER_TYPE = 1
REMINDER__QUERY_TYPE = 2
REMINDER__CALLBACK_TYPE = 3
REMINDER__TYPES = ( (REMINDER__REMINDER_TYPE, "Reminder"), (REMINDER__QUERY_TYPE, "Query"),(REMINDER__CALLBACK_TYPE, "Reminder/Callback") )
REMINDER__DEFAULT_REMINDER_HANDLER = ".app.ReminderHandlerBase"

"""
A Reminder is an instance of a ReminderSchedule.

start_date                  The date to start the reminder_schedule
reminder_schedule           The ReminderSchedule for this Reminder
schedule_iteration_num      The current iteration of the ReminderSchedule (this will be 1 - reminder_schedule.max_iteration_count)
next_event_sequence_num     The sequence number of the next ReminderEvent in the reminder_schedule
try_count                   If the next ReminderEvent has a max_try_count > 0, this is the number of times the ReminderEvent has fired
last_sent_timestamp         The timestamp of the last time a ReminderEvent fired (this is used with try_count to handle timeouts)
active_ind                  True to keep this Reminder active, False to prevent it from firing anymore
"""
class Reminder(models.Model):
    start_date = models.DateField()
    reminder_schedule = models.ForeignKey("ReminderSchedule")
    schedule_iteration_num = models.IntegerField()
    next_event_sequence_num = models.IntegerField()
    try_count = models.IntegerField()
    last_sent_timestamp = models.DateTimeField()
    active_ind = models.BooleanField()
    
    def move_to_next_event(self):
        if self.next_event_sequence_num == self.reminder_schedule.max_sequence_num:
            self.next_event_sequence_num = 1
            self.schedule_iteration_num += 1
            if self.schedule_iteration_num > self.reminder_schedule.max_iteration_count:
                self.active_ind = False
        else:
            self.next_event_sequence_num += 1

"""
A ReminderSchedule is a collection of ReminderEvent objects which define the schedule at
which the text messages should fire.

name                    (optional) A name to describe this ReminderSchedule
max_iteration_count     The number of times this ReminderSchedule should be repeated
schedule_length         The length, in days, of this ReminderSchedule
max_sequence_num        The sequence number of the last ReminderEvent in the ReminderSchedule
"""
class ReminderSchedule(models.Model):
    name = models.CharField(max_length=100,blank=True)
    max_iteration_count = models.IntegerField()
    schedule_length = models.IntegerField()
    max_sequence_num = models.IntegerField()

"""
A ReminderEvent describes a single instance when a text message should be sent.

reminder_schedule       The ReminderSchedule to which this ReminderEvent belongs
sequence_num            The sequence number for this ReminderEvent (should be 1 - reminder_schedule.max_sequence_num)
day_num                 The day offset from the beginning of a reminder_schedule's iteration for when this event should fire (starting with 0)
fire_time               The time of day when this event should fire
type_code               REMINDER__REMINDER_TYPE | REMINDER__CALLBACK_TYPE
sms_text                The text to send
max_try_count           For REMINDER__CALLBACK_TYPE, the maximum number of times to try sending the reminder without getting a response back
timeout_minutes         For REMINDER__CALLBACK_TYPE, the number of minutes to wait before sending the reminder again
"""
class ReminderEvent(models.Model):
    reminder_schedule = models.ForeignKey("ReminderSchedule", related_name="events")
    sequence_num = models.IntegerField()
    day_num = models.IntegerField()
    fire_time = models.TimeField()
    type_code = models.IntegerField(choices=REMINDER__TYPES)
    sms_text = models.CharField(max_length=160, blank=True)
    max_try_count = models.IntegerField()
    timeout_minutes = models.IntegerField()

"""
An instance of the ReminderRecipient class links a Reminder to an application-defined recipient.

reminder    The Reminder
recipient   The recipient of the Reminder, which should be an instance of the class defined by REMINDER__RECIPIENT_CLASS in the application settings
"""
class ReminderRecipient(models.Model):
    reminder = models.ForeignKey("Reminder", related_name="recipients")
    recipient = models.ForeignKey(getattr(settings, "REMINDER__RECIPIENT_CLASS"))

"""
A ReminderCallback object logs the callback response for a Reminder with type REMINDER__CALLBACK_TYPE.

reminder            The Reminder
received_timestamp  The timestamp at which the callback came in
"""
class ReminderCallback(models.Model):
    reminder = models.ForeignKey("Reminder", related_name="callbacks")
    received_timestamp = models.DateTimeField()


# Used for test purposed only
class ReminderDummyRecipient(models.Model):
    mobile_number = models.CharField(max_length=50)

