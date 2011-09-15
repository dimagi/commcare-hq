from datetime import timedelta, datetime
import re
from couchdbkit.ext.django.schema import *
from casexml.apps.case.models import CommCareCase
from corehq.apps.sms.util import send_sms
from corehq.apps.users.models import CommCareUser
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
        if not reminder:
            if self.start_offset >= 0:
                if self.condition_reached(case, self.start, now):
                    reminder = self.spawn_reminder(case, now)
            else:
                try:
                    start = case.get_case_property(self.start)
                except Exception:
                    pass
                else:
                    reminder = self.spawn_reminder(case, self.start)
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
    def get_due_reminders(cls, now):
        return CaseReminder.view('reminders/by_next_fire',
            endkey=json_format_datetime(now),
            include_docs=True
        )
    
    @classmethod
    def fire_reminders(cls, now=None):
        now = now or cls.get_now()
        for reminder in cls.get_due_reminders(now):
            handler = reminder.handler
            handler.fire(reminder)
            handler.set_next_fire(reminder, now)
            reminder.save()

    def retire(self):
        reminders = self.get_reminders()
        self.doc_type += "-Deleted"
        for reminder in reminders:
            reminder.doc_type += "-Deleted"
            reminder.save()
        self.save()

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

from .signals import *