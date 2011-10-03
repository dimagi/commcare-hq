from datetime import timedelta, datetime, date
import re
from couchdbkit.ext.django.schema import *
from django.conf import settings
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.api import send_sms
from corehq.apps.users.models import CommCareUser
import logging
from dimagi.utils.parsing import string_to_datetime, json_format_datetime

def is_true_value(val):
    return val == 'ok' or val == 'OK'

class MessageVariable(object):
    def __init__(self, variable):
        self.variable = variable

    def __unicode__(self):
        return unicode(self.variable)

    @property
    def days_until(self):
        try: variable = string_to_datetime(self.variable)
        except Exception:
            return "(?)"
        else:
            # add 12 hours and then floor == round to the nearest day
            return (variable - datetime.utcnow() + timedelta(hours=12)).days

    def __getattr__(self, item):
        try:
            return super(MessageVariable, self).__getattribute__(item)
        except Exception:
            pass
        try:
            return MessageVariable(getattr(self.variable, item))
        except Exception:
            pass
        try:
            return MessageVariable(self.variable[item])
        except Exception:
            pass
        return "(?)"

class Message(object):
    def __init__(self, template, **params):
        self.template = template
        self.params = {}
        for key, value in params.items():
            self.params[key] = MessageVariable(value)
    def __unicode__(self):
        return self.template.format(**self.params)

    @classmethod
    def render(cls, template, **params):
        if isinstance(template, str):
            template = unicode(template, encoding='utf-8')
        return unicode(cls(template, **params))
    
METHOD_CHOICES = ["sms", "email", "test"]

class CaseReminderHandler(Document):
    domain = StringProperty()
    case_type = StringProperty()

    nickname = StringProperty()
    
    start = StringProperty()            # e.g. "edd" => create reminder on edd
                                           # | "form_started" => create reminder when form_started = 'ok'
    start_offset = IntegerProperty()    # e.g. 3 => three days after edd
    frequency = IntegerProperty()       # e.g. 3 => every 3 days
    until = StringProperty()            # e.g. "edd" => until today > edd
                                        #    | "followup_1_complete" => until followup_1_complete = 'ok'
    message = DictProperty()            # {"en": "Hello, {user.full_name}, you're having issues."}

    lang_property = StringProperty()    # "lang" => check for user.user_data.lang
    default_lang = StringProperty()     # lang to use in case can't find other

    method = StringProperty(choices=METHOD_CHOICES, default="sms")

    @classmethod
    def get_now(cls):
        try:
            # for testing purposes only!
            return getattr(cls, 'now')
        except Exception:
            return datetime.utcnow()

    def get_reminder(self, case):
        domain = self.domain
        handler_id = self._id
        case_id = case._id
        
        return CaseReminder.view('reminders/by_domain_handler_case',
            key=[domain, handler_id, case_id],
            include_docs=True,
        ).one()

    def get_reminders(self):
        domain = self.domain
        handler_id = self._id
        return CaseReminder.view('reminders/by_domain_handler_case',
            startkey=[domain, handler_id],
            endkey=[domain, handler_id, {}],
            include_docs=True,
        ).all()

    def spawn_reminder(self, case, now):
        return CaseReminder(
            domain=self.domain,
            case_id=case._id,
            handler_id=self._id,
            user_id=case.user_id,
            method=self.method,
            next_fire=now + timedelta(days=self.start_offset),
            active=True,
            lang=self.default_lang,
        )

    def set_next_fire(self, reminder, now):
        """
        Sets reminder.next_fire to the next allowable date after now

        This is meant to skip reminders that were just never sent i.e. because the
        reminder went dormant for a while [active=False] rather than sending one
        every minute until they're all made up for

        """
        while now >= reminder.next_fire:
            reminder.next_fire += timedelta(days=self.frequency)

    def should_fire(self, reminder, now):
        return now > reminder.next_fire

    def fire(self, reminder):
        reminder.last_fired = self.get_now()
        message = self.message.get(reminder.lang, self.message[self.default_lang])
        message = Message.render(message, case=reminder.case.case_properties())
        if reminder.method == "sms":
            try:
                phone_number = reminder.user.phone_number
            except Exception:
                phone_number = ''

            send_sms(reminder.domain, reminder.user_id, phone_number, message)
        

    @classmethod
    def condition_reached(cls, case, case_property, now):
        """
        if case[case_property] is 'ok' or a date later than now then True, else False

        """
        condition = case.get_case_property(case_property)
        try: condition = string_to_datetime(condition)
        except Exception:
            pass

        if (isinstance(condition, datetime) and condition > now) or is_true_value(condition):
            return True
        else:
            return False

    def case_changed(self, case, now=None):
        now = now or self.get_now()
        reminder = self.get_reminder(case)

        if case.closed or not CommCareUser.get_by_user_id(case.user_id):
            if reminder:
                reminder.retire()
        else:
            if not reminder:
                start = case.get_case_property(self.start)
                try: start = string_to_datetime(start)
                except Exception:
                    pass
                if isinstance(start, date) or isinstance(start, datetime):
                    if isinstance(start, date):
                        start = datetime(start.year, start.month, start.day, now.hour, now.minute, now.second, now.microsecond)
                    try:
                        reminder = self.spawn_reminder(case, start)
                    except Exception:
                        if settings.DEBUG:
                            raise
                        logging.error(
                            "Case ({case._id}) submitted against "
                            "CaseReminderHandler {self.nickname} ({self._id}) "
                            "but failed to resolve case.{self.start} to a date"
                        )
                else:
                    if self.condition_reached(case, self.start, now):
                        reminder = self.spawn_reminder(case, now)
            else:
                active = not self.condition_reached(case, self.until, now)
                if active and not reminder.active:
                    # if a reminder is reactivated, sending starts over from right now
                    reminder.next_fire = now
                reminder.active = active
            if reminder:
                try:
                    reminder.lang = reminder.user.user_data.get(self.lang_property) or self.default_lang
                except Exception:
                    reminder.lang = self.default_lang
                reminder.save()

    def save(self, **params):
        super(CaseReminderHandler, self).save(**params)
        if not self.deleted():
            cases = CommCareCase.view('hqcase/open_cases',
                reduce=False,
                startkey=[self.domain],
                endkey=[self.domain, {}],
                include_docs=True,
            )
            for case in cases:
                self.case_changed(case)
    @classmethod
    def get_handlers(cls, domain, case_type=None):
        key = [domain]
        if case_type:
            key.append(case_type)
        return cls.view('reminders/handlers_by_domain_case_type',
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
        )

    @classmethod
    def get_all_reminders(cls, domain=None, due_before=None):
        if due_before:
            now_json = json_format_datetime(due_before)
        else:
            now_json = {}

        # domain=None will actually get them all, so this works smoothly
        return CaseReminder.view('reminders/by_next_fire',
            startkey=[domain],
            endkey=[domain, now_json],
            include_docs=True
        ).all()
    
    @classmethod
    def fire_reminders(cls, now=None):
        now = now or cls.get_now()
        for reminder in cls.get_all_reminders(due_before=now):
            handler = reminder.handler
            handler.fire(reminder)
            handler.set_next_fire(reminder, now)
            reminder.save()

    def retire(self):
        reminders = self.get_reminders()
        self.doc_type += "-Deleted"
        for reminder in reminders:
            print "Retiring %s" % reminder._id
            reminder.retire()
        self.save()

    def deleted(self):
        return self.doc_type != 'CaseReminderHandler'

class CaseReminder(Document):
    domain = StringProperty()
    case_id = StringProperty() # to a CommCareCase
    handler_id = StringProperty() # to a CaseReminderHandler
    user_id = StringProperty() # to a CommCareUser
    method = StringProperty(choices=METHOD_CHOICES)
    next_fire = DateTimeProperty()
    last_fired = DateTimeProperty()
    active = BooleanProperty(default=False)
    lang = StringProperty()

    @property
    def handler(self):
        return CaseReminderHandler.get(self.handler_id)

    @property
    def case(self):
        return CommCareCase.get(self.case_id)

    @property
    def user(self):
        return CommCareUser.get_by_user_id(self.user_id)

    def retire(self):
        self.doc_type += "-Deleted"
        self.save()
from .signals import *