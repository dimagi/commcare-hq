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
