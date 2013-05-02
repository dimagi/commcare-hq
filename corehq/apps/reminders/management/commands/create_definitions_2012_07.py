import hashlib
from django.core.management.base import LabelCommand, CommandError
from corehq.apps.reminders.models import CaseReminderHandler, CaseReminderEvent, MATCH_EXACT, MATCH_REGEX, EVENT_AS_SCHEDULE, RECIPIENT_CASE, REPEAT_SCHEDULE_INDEFINITELY
from datetime import time

class Command(LabelCommand):
    help = "Creates reminder definitions."
    args = "<domain>"
    label = ""

    def handle(self, *args, **options):
        if len(args) == 0 or len(args) > 1:
            raise CommandError("Usage: manage.py create_definitions_2012_07 <domain>")
        
        domain = args[0]
        case_type = "participant"
        times_of_day = {
            "0600" : time(6,0,0),
            "0900" : time(9,0,0),
            "1700" : time(17,0,0),
            "2100" : time(21,0,0)
        }
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for time_code, actual_time in times_of_day.items():
            c = CaseReminderHandler(
                domain                  = domain,
                case_type               = case_type,
                nickname                = "Group 1, @ " + time_code,
                default_lang            = "en",
                method                  = "survey",
                ui_type                 = "COMPLEX",
                recipient               = "CASE",
                start_property          = "send_normal_message",
                start_value             = time_code,
                start_date              = "normal_result_message_date",
                start_offset            = 0,
                start_match_type        = "EXACT",
                events                  = [CaseReminderEvent(
                                            day_num                     = 0,
                                            fire_time                   = actual_time,
                                            message                     = {},
                                            callback_timeout_intervals  = [],
                                            form_unique_id              = ""
                                          )],
                schedule_length         = 1,
                event_interpretation    = "SCHEDULE",
                max_iteration_count     = 1,
                until                   = None
            )
            c.save()
            print "Created " + c.nickname
            
            for day in days:
                c = CaseReminderHandler(
                    domain                  = domain,
                    case_type               = case_type,
                    nickname                = "Group 2 - 4, " + day + ", @ " + time_code,
                    default_lang            = "en",
                    method                  = "survey",
                    ui_type                 = "COMPLEX",
                    recipient               = "CASE",
                    start_property          = "send_" + day.lower(),
                    start_value             = time_code,
                    start_date              = day.lower() + "_date",
                    start_offset            = 0,
                    start_match_type        = "EXACT",
                    events                  = [CaseReminderEvent(
                                                day_num                     = 0,
                                                fire_time                   = actual_time,
                                                message                     = {},
                                                callback_timeout_intervals  = [],
                                                form_unique_id              = ""
                                              )],
                    schedule_length         = 1,
                    event_interpretation    = "SCHEDULE",
                    max_iteration_count     = 1,
                    until                   = None
                )
                c.save()
                print "Created " + c.nickname


