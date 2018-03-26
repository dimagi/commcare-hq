from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime, time
from functools import wraps

from couchdbkit.resource import ResourceNotFound
from django.http import Http404
from django.utils.translation import ugettext as _

from corehq import privileges
from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app, get_app_ids_in_domain
from corehq.apps.app_manager.models import Form
from corehq.apps.casegroups.models import CommCareCaseGroup
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.sms.mixin import apply_leniency, CommCareMobileContactMixin, InvalidFormatException
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.form_processor.utils import is_commcarecase
from corehq.util.quickcache import quickcache
from django_prbac.utils import has_privilege


class DotExpandedDict(dict):
    """

    A special dictionary constructor that takes a dictionary in which the keys
    may contain dots to specify inner dictionaries. It's confusing, but this
    example should make sense.

    Taken from last version of the class, removed in Django 1.5
    https://github.com/django/django/blob/0f57935bcd8cd525d8d661c5af4fb70b79e126ae/django/utils/datastructures.py

    >>> d = DotExpandedDict({'person.1.firstname': ['Simon'], \
            'person.1.lastname': ['Willison'], \
            'person.2.firstname': ['Adrian'], \
            'person.2.lastname': ['Holovaty']})
    >>> d
    {'person': {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}}
    >>> d['person']
    {'1': {'lastname': ['Willison'], 'firstname': ['Simon']}, '2': {'lastname': ['Holovaty'], 'firstname': ['Adrian']}}
    >>> d['person']['1']
    {'lastname': ['Willison'], 'firstname': ['Simon']}

    # Gotcha: Results are unpredictable if the dots are "uneven":
    >>> DotExpandedDict({'c.1': 2, 'c.2': 3, 'c': 1})
    {'c': 1}
    """

    def __init__(self, key_to_list_mapping):
        for k, v in key_to_list_mapping.items():
            current = self
            bits = k.split('.')
            for bit in bits[:-1]:
                current = current.setdefault(bit, {})
            # Now assign value to current position
            try:
                current[bits[-1]] = v
            except TypeError: # Special-case if current isn't a dict.
                current = {bits[-1]: v}


def get_form_list(domain):
    form_list = []
    for app_id in get_app_ids_in_domain(domain):
        latest_app = get_app(domain, app_id, latest=True)
        if latest_app.doc_type == "Application":
            for m in latest_app.get_modules():
                for f in m.get_forms():
                    form_list.append({"code": f.unique_id, "name": f.full_path_name})
    return form_list


def get_form_name(form_unique_id):
    try:
        form = Form.get_form(form_unique_id)
    except ResourceNotFound:
        return _("[unknown]")

    return form.full_path_name


def get_recipient_name(recipient, include_desc=True):
    if recipient is None:
        return "(no recipient)"
    elif isinstance(recipient, list):
        if len(recipient) > 0:
            return ",".join([get_recipient_name(r, include_desc) for r in recipient])
        else:
            return "(no recipient)"
    elif isinstance(recipient, CouchUser):
        name = recipient.raw_username
        desc = "User"
    elif is_commcarecase(recipient):
        name = recipient.name
        desc = "Case"
    elif isinstance(recipient, Group):
        name = recipient.name
        desc = "Group"
    elif isinstance(recipient, CommCareCaseGroup):
        name = recipient.name
        desc = "Case Group"
    elif isinstance(recipient, SQLLocation):
        name = recipient.name
        desc = "Location"
    else:
        name = "(unknown)"
        desc = ""
    
    if include_desc:
        return "%s '%s'" % (desc, name)
    else:
        return name


def enqueue_reminder_directly(reminder):
    from corehq.apps.reminders.management.commands.run_reminder_queue import (
        ReminderEnqueuingOperation)
    ReminderEnqueuingOperation().enqueue_directly(reminder)


def create_immediate_reminder(contact, content_type, reminder_type=None,
        message=None, form_unique_id=None, case=None, logged_event=None):
    """
    contact - the contact to send to
    content_type - METHOD_SMS or METHOD_SMS_SURVEY (see corehq.apps.reminders.models)
    reminder_type - either REMINDER_TYPE_DEFAULT, REMINDER_TYPE_ONE_TIME, or REMINDER_TYPE_KEYWORD_INITIATED
    message - the message to send if content_type == METHOD_SMS
    form_unique_id - the form_unique_id of the form to send if content_type == METHOD_SMS_SURVEY
    case - the case that is associated with this reminder (so that you can embed case properties into the message)
    logged_event - if this reminder is being created as a subevent of a
        MessagingEvent, this is the MessagingEvent
    """
    from corehq.apps.reminders.models import (
        CaseReminderHandler,
        CaseReminderEvent,
        ON_DATETIME,
        EVENT_AS_OFFSET,
        REMINDER_TYPE_DEFAULT,
        REMINDER_TYPE_KEYWORD_INITIATED,
        METHOD_SMS,
        METHOD_SMS_SURVEY,
        RECIPIENT_CASE,
        RECIPIENT_USER,
        RECIPIENT_SURVEY_SAMPLE,
        RECIPIENT_USER_GROUP,
    )
    if is_commcarecase(contact):
        recipient = RECIPIENT_CASE
    elif isinstance(contact, CommCareCaseGroup):
        recipient = RECIPIENT_SURVEY_SAMPLE
    elif isinstance(contact, CommCareUser):
        recipient = RECIPIENT_USER
    elif isinstance(contact, Group):
        recipient = RECIPIENT_USER_GROUP
    else:
        raise Exception("Unsupported contact type for %s" % contact._id)

    reminder_type = reminder_type or REMINDER_TYPE_DEFAULT
    if recipient == RECIPIENT_CASE:
        case_id = contact.case_id
    elif case is not None:
        case_id = case.case_id
    else:
        case_id = None

    handler = CaseReminderHandler(
        domain=contact.domain,
        reminder_type=reminder_type,
        nickname="One-time Reminder",
        default_lang="xx",
        method=content_type,
        recipient=recipient,
        start_condition_type=ON_DATETIME,
        start_datetime=datetime.utcnow(),
        start_offset=0,
        events = [CaseReminderEvent(
            day_num=0,
            fire_time=time(0, 0),
            form_unique_id=form_unique_id if content_type == METHOD_SMS_SURVEY else None,
            message={'xx': message} if content_type == METHOD_SMS else {},
            callback_timeout_intervals = [],
        )],
        schedule_length=1,
        event_interpretation=EVENT_AS_OFFSET,
        max_iteration_count=1,
        case_id=case_id,
        user_id=contact.get_id if recipient == RECIPIENT_USER else None,
        sample_id=contact.get_id if recipient == RECIPIENT_SURVEY_SAMPLE else None,
        user_group_id=contact.get_id if recipient == RECIPIENT_USER_GROUP else None,
        messaging_event_id=logged_event.pk if logged_event else None,
    )
    handler.save(send_immediately=True)


def can_use_survey_reminders(request):
    return has_privilege(request, privileges.INBOUND_SMS)


def get_two_way_number_for_recipient(recipient):
    if isinstance(recipient, CommCareMobileContactMixin):
        two_way_numbers = recipient.get_two_way_numbers()
        if len(two_way_numbers) == 1:
            return list(two_way_numbers.values())[0]
        elif len(two_way_numbers) > 1:
            # Retrieve the two-way number that's highest up in the list
            if isinstance(recipient, CouchUser):
                for phone in recipient.phone_numbers:
                    if phone in two_way_numbers:
                        return two_way_numbers[phone]
                raise Exception("Phone number list and PhoneNumber entries are out "
                    "of sync for user %s" % recipient.get_id)
            else:
                raise Exception("Expected a CouchUser")
    return None


def get_one_way_number_for_recipient(recipient):
    if isinstance(recipient, CouchUser):
        return recipient.phone_number
    elif is_commcarecase(recipient):
        one_way_number = recipient.get_case_property('contact_phone_number')
        one_way_number = apply_leniency(one_way_number)
        if one_way_number:
            try:
                CommCareMobileContactMixin.validate_number_format(one_way_number)
                return one_way_number
            except InvalidFormatException:
                return None
    return None


def get_preferred_phone_number_for_recipient(recipient):
    return get_two_way_number_for_recipient(recipient) or get_one_way_number_for_recipient(recipient)


@quickcache(['reminder_id'], timeout=60 * 60 * 24 * 7 * 5)
def get_reminder_domain(reminder_id):
    """
    A reminder instance's domain should never change once set, so
    we can use a very long timeout.
    """
    from corehq.apps.reminders.models import CaseReminder
    return CaseReminder.get(reminder_id).domain


def requires_old_reminder_framework():
    def decorate(fn):
        @wraps(fn)
        def wrapped(request, *args, **kwargs):
            if (
                hasattr(request, 'couch_user') and
                toggles.NEW_REMINDERS_MIGRATOR.enabled(request.couch_user.username)
            ):
                return fn(request, *args, **kwargs)
            if not hasattr(request, 'project'):
                request.project = Domain.get_by_name(request.domain)
            if not request.project.uses_new_reminders:
                return fn(request, *args, **kwargs)
            raise Http404()
        return wrapped
    return decorate
