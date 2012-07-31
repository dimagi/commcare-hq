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
            raise CommandError("Usage: manage.py create_definitions_2012_04 <domain>")
        
        domain = args[0]
        case_type = "patient"
        times_of_day = {
            "0000" : time(0,0,0),
            "0600" : time(6,0,0),
            "0700" : time(7,0,0),
            "0800" : time(8,0,0),
            "1100" : time(11,0,0),
            "1200" : time(12,0,0),
            "1900" : time(19,0,0),
            "2000" : time(20,0,0),
            "2100" : time(21,0,0),
        }
        message = {
            "xx" : "{case.personal_message}",
            "en" : "Please call back to this number."
        }
        default_language = "en"
        callback_timeouts = [60, 30]
        day_list = [0, 1, 2, 3, 4, 5, 6]
        
        # Create reminder definitions
        
        for time_code, actual_time in times_of_day.items():
            
            time_decription = time_code[:2] + ":" + time_code[2:]
            
            # Daily for 8 weeks
            
            CaseReminderHandler(
                domain                  = domain,
                case_type               = case_type,
                nickname                = "Daily, 8 Weeks @ " + time_decription,
                default_lang            = default_language,
                method                  = "callback",
                recipient               = RECIPIENT_CASE,
                start_property          = "daily_schedule",
                start_value             = time_code,
                start_date              = "start_date",
                start_offset            = 0,
                start_match_type        = MATCH_EXACT,
                events                  = [
                    CaseReminderEvent(
                        day_num                     = 0,
                        fire_time                   = actual_time,
                        message                     = message,
                        callback_timeout_intervals  = callback_timeouts
                    )
                ],
                schedule_length         = 1, 
                event_interpretation    = EVENT_AS_SCHEDULE,
                max_iteration_count     = 56,
                until                   = None
            ).save()
            
            # Daily, indefinitely
            
            CaseReminderHandler(
                domain                  = domain,
                case_type               = case_type,
                nickname                = "Daily @ " + time_decription,
                default_lang            = default_language,
                method                  = "callback",
                recipient               = RECIPIENT_CASE,
                start_property          = "daily_schedule",
                start_value             = "indefinite_" + time_code,
                start_date              = "start_date",
                start_offset            = 0,
                start_match_type        = MATCH_EXACT,
                events                  = [
                    CaseReminderEvent(
                        day_num                     = 0,
                        fire_time                   = actual_time,
                        message                     = message,
                        callback_timeout_intervals  = callback_timeouts
                    )
                ],
                schedule_length         = 1, 
                event_interpretation    = EVENT_AS_SCHEDULE,
                max_iteration_count     = -1,
                until                   = "stop_date"
            ).save()
            
            for day in day_list:
            
                # 3 per week schedules
                
                CaseReminderHandler(
                    domain                  = domain,
                    case_type               = case_type,
                    nickname                = "Three Per Week @ " + time_decription,
                    default_lang            = default_language,
                    method                  = "callback",
                    recipient               = RECIPIENT_CASE,
                    start_property          = "tpw_schedule",
                    start_value             = "^({0}\d\d|\d{0}\d|\d\d{0})_".format(day) + time_code + "$",
                    start_date              = "start_date",
                    start_offset            = 56,
                    start_match_type        = MATCH_REGEX,
                    events                  = [
                        CaseReminderEvent(
                            day_num                     = day,
                            fire_time                   = actual_time,
                            message                     = message,
                            callback_timeout_intervals  = callback_timeouts
                        )
                    ],
                    schedule_length         = 7, 
                    event_interpretation    = EVENT_AS_SCHEDULE,
                    max_iteration_count     = 8,
                    until                   = None
                ).save()
                
                # 1 per week schedules
                
                CaseReminderHandler(
                    domain                  = domain,
                    case_type               = case_type,
                    nickname                = "One Per Week @ " + time_decription,
                    default_lang            = default_language,
                    method                  = "callback",
                    recipient               = RECIPIENT_CASE,
                    start_property          = "opw_schedule",
                    start_value             = "{0}_".format(day) + time_code,
                    start_date              = "start_date",
                    start_offset            = 112,
                    start_match_type        = MATCH_EXACT,
                    events                  = [
                        CaseReminderEvent(
                            day_num                     = day,
                            fire_time                   = actual_time,
                            message                     = message,
                            callback_timeout_intervals  = callback_timeouts
                        )
                    ],
                    schedule_length         = 7, 
                    event_interpretation    = EVENT_AS_SCHEDULE,
                    max_iteration_count     = 32,
                    until                   = None
                ).save()



