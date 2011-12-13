from .models import *

"""
Creates a ReminderSchedule along with its corresponding ReminderEvents based
on the given information.

Parameters:
    max_iteration_count - the number of times the schedule should be repeated
    schedule_length     - the length, in days, of the schedule
    eventinfo           - a list containing information for each reminder event with the following structure:
                          [ ... , [day_num, fire_time, sms_text] , ... ]
                          day_num is the day offset from the beginning of the schedule
                          fire_time is the time to fire the reminder
                          sms_text is the text to send
Return:
    The ReminderSchedule which was just created.

"""
def create_reminder_schedule(max_iteration_count, schedule_length, eventinfo):
    schedule = ReminderSchedule(
        max_iteration_count=max_iteration_count
       ,schedule_length=schedule_length
       ,max_sequence_num=0
    )
    schedule.save()
    counter = 1
    for e in eventinfo:
        event = ReminderEvent(
            reminder_schedule=schedule
           ,sequence_num=counter
           ,day_num=e[0]
           ,fire_time=e[1]
           ,type_code=REMINDER__REMINDER_TYPE
           ,sms_text=e[2]
        )
        counter += 1
        event.save()
    schedule.max_sequence_num = counter - 1
    schedule.save()
    return schedule

"""
Creates a ReminderSchedule for a one-time reminder.

Parameters:
    fire_time   - the time of day which the reminder should fire
    sms_text    - the text to send

Return:
    The ReminderSchedule which was just created.

"""
def create_one_time_reminder_schedule(fire_time, sms_text):
    return create_reminder_schedule(1, 1, [[0, fire_time, sms_text]])

"""
Creates a once-a-day ReminderSchedule.

Parameters:
    num_reminders   - the total number of reminders to send out
    day_offset      - the days between sending each reminder; 1 for daily, 2 for every other day, etc.
    fire_time       - the time each day to fire the reminder
    sms_text        - the text to send on each reminder

Return:
    The ReminderSchedule which was just created.

"""
def create_daily_reminder_schedule(num_reminders, day_offset, fire_time, sms_text):
    return create_reminder_schedule(num_reminders, day_offset, [[0, fire_time, sms_text]])

"""
Creates a Reminder with the given ReminderSchedule and recipient.

Parameters:
    start_date          - the day on which to start the ReminderSchedule
    reminder_schedule   - the ReminderSchedule to use for this Reminder
    recipients          - a list of recipients for this Reminder; this should be a list of instances of the REMINDER__RECIPIENT_CLASS
                          specified in your settings

Return:
    The Reminder which was just created.
"""
def create_reminder(start_date, reminder_schedule, recipients):
    r = Reminder(
        start_date=start_date
       ,reminder_schedule=reminder_schedule
       ,schedule_iteration_num=1
       ,next_event_sequence_num=1
       ,active_ind=True
    )
    r.save()
    
    for recipient in recipients:
        rr = ReminderRecipient(reminder=r, recipient=recipient)
        rr.save()
    
    return r


