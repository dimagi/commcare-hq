import datetime

from .handler import *
from .app import *
from .models import *
from django.db.models import Q
from django.conf import settings

def run():
    handler = ReminderHandlerDefault()
    reminders = Reminder.objects.filter(active_ind = True)
    for r in reminders:
        next_event = ReminderEvent.objects.filter(reminder_schedule = r.reminder_schedule).get(sequence_num = r.next_event_sequence_num)
        day_offset = (r.reminder_schedule.schedule_length * (r.schedule_iteration_num - 1)) + next_event.day_num
        reminder_datetime = datetime.datetime.combine(r.start_date, next_event.fire_time) + datetime.timedelta(days = day_offset)
        if next_event.type_code == REMINDER__CALLBACK_TYPE and r.try_count > 0:
            if ReminderCallback.objects.filter(reminder=r).filter(received_timestamp__gt=reminder_datetime).count() > 0:
                r.move_to_next_event()
            else:
                timeout_datetime = r.last_send_timestamp + datetime.timedelta(minutes = next_event.timeout_minutes)
                if datetime.datetime.now() >= timeout_datetime:
                    r.last_sent_timestamp = datetime.datetime.now()
                    r.try_count += 1
                    r.save()
                    for recipient in r.recipients.all():
                        handler.outgoing_sms(getattr(recipient.recipient, getattr(settings, "REMINDER__RECIPIENT_MOBILE_NUMBER")), next_event.sms_text)
                    if r.try_count >= next_event.max_try_count:
                        r.move_to_next_event()
                        r.save()
            continue
        if next_event.type_code == REMINDER__REMINDER_TYPE or next_event.type_code == REMINDER__CALLBACK_TYPE:
            if datetime.datetime.now() >= reminder_datetime:
                r.move_to_next_event()
                r.last_sent_timestamp = datetime.datetime.now()
                if next_event.max_try_count > 1:
                    r.try_count = 1
                else:
                    r.try_count = 0
                r.save()
                for recipient in r.recipients.all():
                    handler.outgoing_sms(getattr(recipient.recipient, getattr(settings, "REMINDER__RECIPIENT_MOBILE_NUMBER")), next_event.sms_text)

