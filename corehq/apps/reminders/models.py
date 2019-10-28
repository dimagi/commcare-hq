import re
from collections import namedtuple
from datetime import date, datetime, time, timedelta
from random import randint
from string import Formatter

from django.conf import settings
from django.db import models, transaction

import pytz
from couchdbkit import ResourceNotFound
from couchdbkit.exceptions import ResourceConflict
from dateutil.parser import parse

from dimagi.ext.couchdbkit import *
from dimagi.utils.couch import CriticalSection, LockableMixIn
from dimagi.utils.couch.cache.cache_core import get_redis_client
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function
from dimagi.utils.parsing import json_format_datetime, string_to_datetime

from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.groups.models import Group
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.models import MessagingEvent
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.apps.smsforms.util import critical_section_for_smsforms_sessions
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.form_processor.abstract_models import DEFAULT_PARENT_IDENTIFIER
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.utils import is_commcarecase
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import ServerTime, UserTime


class IllegalModelStateException(Exception):
    pass


class UnexpectedConfigurationException(Exception):
    pass


METHOD_SMS = "sms"
METHOD_SMS_CALLBACK = "callback"
METHOD_SMS_SURVEY = "survey"
METHOD_IVR_SURVEY = "ivr_survey"
METHOD_EMAIL = "email"
METHOD_STRUCTURED_SMS = "structured_sms"

METHOD_CHOICES = [
    METHOD_SMS,
    METHOD_SMS_CALLBACK,
    METHOD_SMS_SURVEY,
    METHOD_IVR_SURVEY,
    METHOD_EMAIL,
]

# The Monday - Sunday constants are meant to match the result from
# date.weekday()
DAY_ANY = -1
DAY_MON = 0
DAY_TUE = 1
DAY_WED = 2
DAY_THU = 3
DAY_FRI = 4
DAY_SAT = 5
DAY_SUN = 6

DAY_OF_WEEK_CHOICES = [
    DAY_ANY,
    DAY_MON,
    DAY_TUE,
    DAY_WED,
    DAY_THU,
    DAY_FRI,
    DAY_SAT,
    DAY_SUN,
]

REPEAT_SCHEDULE_INDEFINITELY = -1

EVENT_AS_SCHEDULE = "SCHEDULE"
EVENT_AS_OFFSET = "OFFSET"
EVENT_INTERPRETATIONS = [EVENT_AS_SCHEDULE, EVENT_AS_OFFSET]

UI_SIMPLE_FIXED = "SIMPLE_FIXED"
UI_COMPLEX = "COMPLEX"
UI_CHOICES = [UI_SIMPLE_FIXED, UI_COMPLEX]

RECIPIENT_SENDER = "SENDER"
RECIPIENT_USER = "USER"
RECIPIENT_OWNER = "OWNER"
RECIPIENT_CASE = "CASE"
RECIPIENT_PARENT_CASE = "PARENT_CASE"
RECIPIENT_ALL_SUBCASES = "ALL_SUBCASES"
RECIPIENT_SUBCASE = "SUBCASE"
RECIPIENT_SURVEY_SAMPLE = "SURVEY_SAMPLE"
RECIPIENT_USER_GROUP = "USER_GROUP"
RECIPIENT_LOCATION = "LOCATION"
DEPRECATED_RECIPIENT_CHOICES = [
    'TB_PERSON_CASE_FROM_VOUCHER_CASE',
    'TB_AGENCY_USER_CASE_FROM_VOUCHER_FULFILLED_BY_ID',
    'TB_BENEFICIARY_REGISTRATION_RECIPIENTS',
    'TB_PRESCRIPTION_VOUCHER_ALERT_RECIPIENTS',
]
RECIPIENT_CHOICES = [
    RECIPIENT_USER, RECIPIENT_OWNER, RECIPIENT_CASE, RECIPIENT_SURVEY_SAMPLE,
    RECIPIENT_PARENT_CASE, RECIPIENT_SUBCASE, RECIPIENT_USER_GROUP,
    RECIPIENT_LOCATION
] + list(settings.AVAILABLE_CUSTOM_REMINDER_RECIPIENTS) + DEPRECATED_RECIPIENT_CHOICES

KEYWORD_RECIPIENT_CHOICES = [RECIPIENT_SENDER, RECIPIENT_OWNER, RECIPIENT_USER_GROUP]
KEYWORD_ACTION_CHOICES = [METHOD_SMS, METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS]

FIRE_TIME_DEFAULT = "DEFAULT"
FIRE_TIME_CASE_PROPERTY = "CASE_PROPERTY"
FIRE_TIME_RANDOM = "RANDOM"
FIRE_TIME_CHOICES = [FIRE_TIME_DEFAULT, FIRE_TIME_CASE_PROPERTY, FIRE_TIME_RANDOM]

MATCH_EXACT = "EXACT"
MATCH_REGEX = "REGEX"
MATCH_ANY_VALUE = "ANY_VALUE"
MATCH_TYPE_CHOICES = [MATCH_EXACT, MATCH_REGEX, MATCH_ANY_VALUE]

CASE_CRITERIA = "CASE_CRITERIA"
ON_DATETIME = "ON_DATETIME"
START_CONDITION_TYPES = [CASE_CRITERIA, ON_DATETIME]

SURVEY_METHOD_LIST = ["SMS", "CATI"]

UI_FREQUENCY_ADVANCED = "ADVANCED"
UI_FREQUENCY_CHOICES = [UI_FREQUENCY_ADVANCED]

QUESTION_RETRY_CHOICES = [1, 2, 3, 4, 5]

FORM_TYPE_ONE_BY_ONE = "ONE_BY_ONE" # Answer each question one at a time
FORM_TYPE_ALL_AT_ONCE = "ALL_AT_ONCE" # Complete the entire form with just one sms using the delimiter to separate answers
FORM_TYPE_CHOICES = [FORM_TYPE_ONE_BY_ONE, FORM_TYPE_ALL_AT_ONCE]

REMINDER_TYPE_ONE_TIME = "ONE_TIME"
REMINDER_TYPE_KEYWORD_INITIATED = "KEYWORD_INITIATED"
REMINDER_TYPE_DEFAULT = "DEFAULT"
REMINDER_TYPE_SURVEY_MANAGEMENT = "SURVEY_MANAGEMENT"
REMINDER_TYPE_CHOICES = [REMINDER_TYPE_DEFAULT, REMINDER_TYPE_ONE_TIME,
    REMINDER_TYPE_KEYWORD_INITIATED, REMINDER_TYPE_SURVEY_MANAGEMENT]

SEND_NOW = "NOW"
SEND_LATER = "LATER"


class CaseReminderEvent(DocumentSchema):
    day_num = IntegerProperty()
    fire_time = TimeProperty()
    fire_time_aux = StringProperty()
    fire_time_type = StringProperty(choices=FIRE_TIME_CHOICES, default=FIRE_TIME_DEFAULT)
    time_window_length = IntegerProperty()
    subject = DictProperty()
    message = DictProperty()
    callback_timeout_intervals = ListProperty(IntegerProperty)
    app_id = StringProperty()
    form_unique_id = StringProperty()


class CaseReminderHandler(Document):
    domain = StringProperty()
    last_modified = DateTimeProperty()
    active = BooleanProperty(default=True)
    case_type = StringProperty()
    nickname = StringProperty()
    default_lang = StringProperty()
    method = StringProperty(choices=METHOD_CHOICES, default="sms")
    ui_type = StringProperty(choices=UI_CHOICES, default=UI_SIMPLE_FIXED)
    recipient = StringProperty(choices=RECIPIENT_CHOICES, default=RECIPIENT_USER)
    ui_frequency = StringProperty(choices=UI_FREQUENCY_CHOICES, default=UI_FREQUENCY_ADVANCED) # This will be used to simplify the scheduling process in the ui
    sample_id = StringProperty()
    user_group_id = StringProperty()
    user_id = StringProperty()
    case_id = StringProperty()
    reminder_type = StringProperty(choices=REMINDER_TYPE_CHOICES, default=REMINDER_TYPE_DEFAULT)
    locked = BooleanProperty(default=False)

    # Only used when recipient is RECIPIENT_LOCATION
    # All users belonging to these locations will be recipients
    # Should be a list of (Couch model) Location ids
    location_ids = ListProperty()

    # If True, all users belonging to any child locations of the above
    # locations will also be recipients
    include_child_locations = BooleanProperty(default=False)

    # Only used when recipient is RECIPIENT_SUBCASE.
    # All subcases matching the given criteria will be the recipients.
    recipient_case_match_property = StringProperty()
    recipient_case_match_type = StringProperty(choices=MATCH_TYPE_CHOICES)
    recipient_case_match_value = StringProperty()
    
    # Only applies when method is "survey".
    # If this is True, on the last survey timeout, instead of resending the current question, 
    # it will submit the form for the recipient with whatever is completed up to that point.
    submit_partial_forms = BooleanProperty(default=False)
    
    # Only applies when submit_partial_forms is True.
    # If this is True, partial form submissions will be allowed to create / update / close cases.
    # If this is False, partial form submissions will just submit the form without case create / update / close.
    include_case_side_effects = BooleanProperty(default=False)
    
    # Only applies for method = "ivr_survey" right now.
    # This is the maximum number of times that it will retry asking a question with an invalid response before hanging
    # up. This is meant to prevent long running calls.
    max_question_retries = IntegerProperty(choices=QUESTION_RETRY_CHOICES, default=QUESTION_RETRY_CHOICES[-1])
    
    survey_incentive = StringProperty()
    
    # start condition
    start_condition_type = StringProperty(choices=START_CONDITION_TYPES, default=CASE_CRITERIA)
    
    # used when start_condition_type == ON_DATETIME
    start_datetime = DateTimeProperty()
    
    # used when start_condition_type == CASE_CRITERIA
    start_property = StringProperty()
    start_value = StringProperty()
    start_date = StringProperty()
    start_offset = IntegerProperty()
    start_match_type = StringProperty(choices=MATCH_TYPE_CHOICES)
    start_day_of_week = IntegerProperty(choices=DAY_OF_WEEK_CHOICES,
        default=DAY_ANY)
    
    # reminder schedule
    events = SchemaListProperty(CaseReminderEvent)
    schedule_length = IntegerProperty()
    event_interpretation = StringProperty(choices=EVENT_INTERPRETATIONS, default=EVENT_AS_OFFSET)
    max_iteration_count = IntegerProperty()
    
    # stop condition
    until = StringProperty()

    # If present, references an entry in settings.ALLOWED_CUSTOM_CONTENT_HANDLERS, which maps to a function
    # that should be called to retrieve the sms content to send in an sms reminder.
    # The signature of a custom content handler should be function(reminder, handler, recipient)
    custom_content_handler = StringProperty()

    #   If a subcase triggers an SMS survey, but we're sending it to the parent case,
    # we sometimes want the subcase to be the one on which we execute case actions
    # during form submission. This option will allow for that.
    #   Note that this option only makes a difference if a case is filling out the SMS survey,
    # and if a case other than that case triggered the reminder.
    force_surveys_to_use_triggered_case = BooleanProperty(default=False)

    # If this reminder definition is being created as a subevent of a
    # MessagingEvent, this is the id of the MessagingEvent
    messaging_event_id = IntegerProperty()

    # Set this property to filter the recipient list using custom user data.
    # Should be a dictionary where each key is the name of the custom user data
    # field, and each value is a list of allowed values to filter on.
    # For example, if set to:
    #   {'nickname': ['bob', 'jim'],
    #    'phone_type': ['android']}
    # then the recipient list would be filtered to only include users whose phone
    # type is android and whose nickname is either bob or jim.
    # If {}, then no filter is applied to the recipient list.
    user_data_filter = DictProperty()

    # When sending a case criteria reminder whose start date is defined in
    # a case property, this option tells what to do if that start date case
    # property is blank or unparseable.  If set to True, we use today's date.
    # If False, we don't schedule any reminder at all.
    use_today_if_start_date_is_blank = BooleanProperty(default=True)


class CaseReminder(SafeSaveDocument, LockableMixIn):
    """
    Where the CaseReminderHandler is the rule and schedule for sending out reminders,
    a CaseReminder is an instance of that rule as it is being applied to a specific
    CommCareCase. A CaseReminder only applies to a single CommCareCase/CaseReminderHandler
    interaction and is just a representation of the state of the rule in the lifecycle 
    of the CaseReminderHandler.
    """
    domain = StringProperty()                       # Domain
    last_modified = DateTimeProperty()
    case_id = StringProperty()                      # Reference to the CommCareCase
    handler_id = StringProperty()                   # Reference to the CaseReminderHandler
    user_id = StringProperty()                      # Reference to the CouchUser who will receive the SMS messages
    method = StringProperty(choices=METHOD_CHOICES) # See CaseReminderHandler.method
    next_fire = DateTimeProperty()                  # The date and time that the next message should go out
    last_fired = DateTimeProperty()                 # The date and time that the last message went out
    active = BooleanProperty(default=False)         # True if active, False if deactivated
    start_date = DateProperty()                     # For CaseReminderHandlers with event_interpretation=SCHEDULE, this is the date (in the recipient's time zone) from which all event times are calculated
    schedule_iteration_num = IntegerProperty()      # The current iteration through the cycle of self.handler.events
    current_event_sequence_num = IntegerProperty()  # The current event number (index to self.handler.events)
    callback_try_count = IntegerProperty()          # Keeps track of the number of times a callback has timed out
    skip_remaining_timeouts = BooleanProperty()     # An event handling method can set this to True to skip the remaining timeout intervals for the current event
    start_condition_datetime = DateTimeProperty()   # The date and time matching the case property specified by the CaseReminderHandler.start_condition
    sample_id = StringProperty()
    xforms_session_ids = ListProperty(StringProperty)
    error_retry_count = IntegerProperty(default=0)
    last_scheduled_fire_time = DateTimeProperty()
    event_initiation_timestamp = DateTimeProperty() # The date and time that the event was started (which is the same throughout all timeouts)
    error = BooleanProperty(default=False)
    error_msg = StringProperty()

    # This is the id of the MessagingEvent that was created the
    # last time an event for this reminder fired.
    last_messaging_event_id = IntegerProperty()


class SurveyKeywordAction(DocumentSchema):
    recipient = StringProperty(choices=KEYWORD_RECIPIENT_CHOICES)
    recipient_id = StringProperty()
    action = StringProperty(choices=KEYWORD_ACTION_CHOICES)

    # Only used for action == METHOD_SMS
    message_content = StringProperty()

    # Only used for action in [METHOD_SMS_SURVEY, METHOD_STRUCTURED_SMS]
    app_id = StringProperty()
    form_unique_id = StringProperty()

    # Only used for action == METHOD_STRUCTURED_SMS
    use_named_args = BooleanProperty()
    named_args = DictProperty() # Dictionary of {argument name in the sms (caps) : form question xpath}
    named_args_separator = StringProperty() # Can be None in which case there is no separator (i.e., a100 b200)


class SurveyKeyword(Document):
    domain = StringProperty()
    keyword = StringProperty()
    description = StringProperty()
    actions = SchemaListProperty(SurveyKeywordAction)
    delimiter = StringProperty() # Only matters if this is a structured SMS: default is None, in which case the delimiter is any consecutive white space
    override_open_sessions = BooleanProperty()
    initiator_doc_type_filter = ListProperty(StringProperty) # List of doc types representing the only types of contacts who should be able to invoke this keyword. Empty list means anyone can invoke.

    # Properties needed for migration and then can be removed
    form_type = StringProperty(choices=FORM_TYPE_CHOICES, default=FORM_TYPE_ONE_BY_ONE)
    app_id = StringProperty()
    form_unique_id = StringProperty()
    use_named_args = BooleanProperty()
    named_args = DictProperty()
    named_args_separator = StringProperty()
    oct13_migration_timestamp = DateTimeProperty()

    def is_structured_sms(self):
        return METHOD_STRUCTURED_SMS in [a.action for a in self.actions]
    
    @property
    def get_id(self):
        return self._id
    
    @classmethod
    def get_keyword(cls, domain, keyword):
        return cls.view("reminders/survey_keywords",
            key = [domain, keyword.upper()],
            include_docs=True,
            reduce=False,
        ).one()

    @classmethod
    def get_by_domain(cls, domain, limit=None, skip=None):
        extra_kwargs = {}
        if limit is not None:
            extra_kwargs['limit'] = limit
        if skip is not None:
            extra_kwargs['skip'] = skip
        return cls.view(
            'reminders/survey_keywords',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
            reduce=False,
            **extra_kwargs
        ).all()

    def save(self, *args, **kwargs):
        self.clear_caches()
        return super(SurveyKeyword, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.clear_caches()
        return super(SurveyKeyword, self).delete(*args, **kwargs)

    def clear_caches(self):
        self.domain_has_keywords.clear(SurveyKeyword, self.domain)

    @classmethod
    @quickcache(['domain'], timeout=60 * 60)
    def domain_has_keywords(cls, domain):
        reduced = cls.view('reminders/survey_keywords',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=True
        ).all()
        count = reduced[0]['value'] if reduced else 0
        return count > 0


class EmailUsage(models.Model):
    domain = models.CharField(max_length=126, db_index=True)
    year = models.IntegerField()
    month = models.IntegerField()
    count = models.IntegerField(default=0)

    class Meta(object):
        unique_together = ('domain', 'year', 'month')
        app_label = "reminders"

    @classmethod
    def get_or_create_usage_record(cls, domain):
        now = datetime.utcnow()
        domain_year_month = '%s-%d-%d' % (
            domain,
            now.year,
            now.month
        )
        email_usage_get_or_create_key = 'get-or-create-email-usage-%s' % domain_year_month

        with CriticalSection([email_usage_get_or_create_key]):
            return cls.objects.get_or_create(
                domain=domain,
                year=now.year,
                month=now.month
            )[0]

    @classmethod
    def get_total_count(cls, domain):
        qs = cls.objects.filter(domain=domain)
        result = qs.aggregate(total=models.Sum('count'))
        return result['total'] or 0

    def update_count(self, increase_by=1):
        # This operation is thread safe, no need to use CriticalSection
        EmailUsage.objects.filter(pk=self.pk).update(count=models.F('count') + increase_by)
