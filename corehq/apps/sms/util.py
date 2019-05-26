from __future__ import absolute_import
from __future__ import unicode_literals
import re
import uuid
import datetime
from couchdbkit import ResourceNotFound
from corehq.apps.translations.models import StandaloneTranslationDoc
from corehq.apps.users.models import CouchUser
from django.conf import settings
from corehq.apps.hqcase.utils import submit_case_block_from_template
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache
from django.core.exceptions import ValidationError
from memoized import memoized
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.modules import to_function
from django.utils.translation import ugettext as _
import six


class DateFormat(object):
    def __init__(self, human_readable_format, c_standard_format, validate_regex):
        self.human_readable_format = human_readable_format
        self.c_standard_format = c_standard_format
        self.validate_regex = validate_regex

    def parse(self, value):
        return datetime.datetime.strptime(value, self.c_standard_format)

    def is_valid(self, value):
        return re.match(self.validate_regex, value) is not None


# A project can specify the expected format of answers to date questions
# in SMS Surveys. These are the available choices.
ALLOWED_SURVEY_DATE_FORMATS = (
    DateFormat('YYYYMMDD', '%Y%m%d', r'^\d{8}$'),
    DateFormat('MMDDYYYY', '%m%d%Y', r'^\d{8}$'),
    DateFormat('DDMMYYYY', '%d%m%Y', r'^\d{8}$'),
)

SURVEY_DATE_FORMAT_LOOKUP = {df.human_readable_format: df for df in ALLOWED_SURVEY_DATE_FORMATS}

phone_number_plus_re = re.compile(r"^\+{0,1}\d+$")


class ContactNotFoundException(Exception):
    pass


def get_date_format(human_readable_format):
    return SURVEY_DATE_FORMAT_LOOKUP.get(human_readable_format, ALLOWED_SURVEY_DATE_FORMATS[0])


def strip_plus(phone_number):
    if (isinstance(phone_number, six.string_types) and len(phone_number) > 0
            and phone_number[0] == "+"):
        soft_assert_type_text(phone_number)
        return phone_number[1:]
    else:
        return phone_number


def clean_phone_number(text):
    """
    strip non-numeric characters and add '%2B' at the front
    """
    non_decimal = re.compile(r'[^\d.]+')
    plus = '+'
    cleaned_text = "%s%s" % (plus, non_decimal.sub('', text))
    return cleaned_text


def validate_phone_number(phone_number, error_message=None):
    if (
        not isinstance(phone_number, six.string_types) or
        not phone_number_plus_re.match(phone_number)
    ):
        error_message = error_message or _("Invalid phone number format.")
        raise ValidationError(error_message)
    soft_assert_type_text(phone_number)


def format_message_list(message_list):
    """
    question = message_list[-1]
    if len(question) > 160:
        return question[0:157] + "..."
    else:
        extra_space = 160 - len(question)
        message_start = ""
        if extra_space > 3:
            for msg in message_list[0:-1]:
                message_start += msg + ". "
            if len(message_start) > extra_space:
                message_start = message_start[0:extra_space-3] + "..."
        return message_start + question
    """
    # Some gateways (yo) allow a longer message to be sent and handle splitting it up on their end, so for now just join all messages together
    return " ".join(message_list)


def register_sms_contact(domain, case_type, case_name, user_id,
        contact_phone_number, contact_phone_number_is_verified="1",
        contact_backend_id=None, language_code=None, time_zone=None,
        owner_id=None, contact_ivr_backend_id=None):
    """
    Creates a messaging case contact by submitting system-generated casexml
    """
    utcnow = str(datetime.datetime.utcnow())
    case_id = str(uuid.uuid3(uuid.NAMESPACE_URL, utcnow))
    if owner_id is None:
        owner_id = user_id
    context = {
        "case_id": case_id,
        "date_modified": json_format_datetime(datetime.datetime.utcnow()),
        "case_type": case_type,
        "case_name": case_name,
        "owner_id": owner_id,
        "user_id": user_id,
        "contact_phone_number": contact_phone_number,
        "contact_phone_number_is_verified": contact_phone_number_is_verified,
        "contact_backend_id": contact_backend_id,
        "language_code": language_code,
        "time_zone": time_zone,
        "contact_ivr_backend_id": contact_ivr_backend_id,
    }
    submit_case_block_from_template(domain, "sms/xml/register_contact.xml", context, user_id=user_id)
    return case_id


def update_contact(domain, case_id, user_id, contact_phone_number=None, contact_phone_number_is_verified=None, contact_backend_id=None, language_code=None, time_zone=None):
    context = {
        "case_id" : case_id,
        "date_modified" : json_format_datetime(datetime.datetime.utcnow()),
        "user_id" : user_id,
        "contact_phone_number" : contact_phone_number,
        "contact_phone_number_is_verified" : contact_phone_number_is_verified,
        "contact_backend_id" : contact_backend_id,
        "language_code" : language_code,
        "time_zone" : time_zone
    }
    submit_case_block_from_template(domain, "sms/xml/update_contact.xml", context, user_id=user_id)


def _get_backend_classes(backend_list):
    """
    Returns a dictionary of {api id: class} for all installed SMS backends.
    """
    from corehq.apps.sms.mixin import BadSMSConfigException
    result = {}

    for backend_class in backend_list:
        cls = to_function(backend_class)
        api_id = cls.get_api_id()
        if api_id in result:
            raise BadSMSConfigException("Cannot have more than one backend with the same "
                                        "api id. Duplicate found for: %s" % api_id)
        result[api_id] = cls
    return result


@memoized
def get_sms_backend_classes():
    return _get_backend_classes(settings.SMS_LOADED_SQL_BACKENDS)


CLEAN_TEXT_REPLACEMENTS = (
    # Common emoticon replacements
    (":o", ": o"),
    (":O", ": O"),
    (":x", ": x"),
    (":X", ": X"),
    (":D", ": D"),
    (":p", ": p"),
    (":P", ": P"),
    # Special punctuation ascii conversion
    ("\u2013", "-"),  # Dash
    ("\u201c", '"'),  # Open double quote
    ("\u201d", '"'),  # Close double quote
    ("\u2018", "'"),  # Open single quote
    ("\u2019", "'"),  # Close single quote
    ("\u2026", "..."),  # Ellipsis
)


def clean_text(text):
    """
    Performs the replacements in CLEAN_TEXT_REPLACEMENTS on text.
    """
    for a, b in CLEAN_TEXT_REPLACEMENTS:
        text = text.replace(a, b)
    return text


def get_contact(domain, contact_id):
    from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
    from corehq.form_processor.exceptions import CaseNotFound
    contact = None
    try:
        contact = CaseAccessors(domain).get_case(contact_id)
    except (ResourceNotFound, CaseNotFound):
        pass

    if contact and contact.doc_type == 'CommCareCase' and contact.domain == domain:
        return contact

    contact = None
    try:
        contact = CouchUser.get_by_user_id(contact_id, domain=domain)
    except CouchUser.AccountTypeError:
        pass

    if not contact:
        raise ContactNotFoundException("Contact not found")

    return contact


def touchforms_error_is_config_error(domain, touchforms_error):
    """
    Returns True if the given TouchformsError is the result of a
    form configuration error.
    """
    # Unfortunately there isn't a better way to do this.
    # What we want to do is try and pick out the types of exceptions
    # that are configuration errors such as an xpath reference error
    # or misconfigured case sharing settings.
    exception_text = touchforms_error.response_data.get('exception') or ''
    exception_text = exception_text.lower()
    return any(s in exception_text for s in (
        'case sharing settings',
        'error in calculation',
        'problem with display condition',
    ))


def get_formplayer_exception(domain, touchforms_error):
    return touchforms_error.response_data.get('exception')


@quickcache(['backend_id'], timeout=5 * 60)
def get_backend_name(backend_id):
    """
    Returns None if the backend is not found, otherwise
    returns the backend's name.
    """
    if not backend_id:
        return None

    from corehq.apps.sms.models import SQLMobileBackend
    try:
        return SQLMobileBackend.load(backend_id, is_couch_id=True).name
    except:
        return None


def set_domain_default_backend_to_test_backend(domain):
    """
    Pass in the name of the domain to set the domain's default
    sms backend to be the test backend.
    """
    from corehq.apps.sms.models import SQLMobileBackend, SQLMobileBackendMapping
    test_backend = SQLMobileBackend.get_global_backend_by_name(
        SQLMobileBackend.SMS,
        'MOBILE_BACKEND_TEST'
    )
    if not test_backend:
        raise Exception("Expected MOBILE_BACKEND_TEST to be created")
    SQLMobileBackendMapping.set_default_domain_backend(
        domain,
        test_backend
    )


@quickcache(['domain', 'case_id'], timeout=60 * 60)
def is_case_contact_active(domain, case_id):
    from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
    from corehq.form_processor.exceptions import CaseNotFound

    try:
        case = CaseAccessors(domain).get_case(case_id)
    except (ResourceNotFound, CaseNotFound):
        return False

    return not (case.closed or case.is_deleted)


@quickcache(['domain', 'user_id'], timeout=60 * 60)
def is_user_contact_active(domain, user_id):
    try:
        user = CouchUser.get_by_user_id(user_id, domain=domain)
    except KeyError:
        return False

    if not user:
        return False

    return user.is_active


def is_contact_active(domain, contact_doc_type, contact_id):
    if contact_doc_type == 'CommCareCase':
        return is_case_contact_active(domain, contact_id)
    elif contact_doc_type in ('CommCareUser', 'WebUser'):
        return is_user_contact_active(domain, contact_id)
    else:
        # We can't tie the contact to a document so since we can't say whether
        # it's inactive, we count it as active
        return True


def get_or_create_translation_doc(domain):
    with StandaloneTranslationDoc.get_locked_obj(domain, 'sms', create=True) as tdoc:
        if len(tdoc.langs) == 0:
            tdoc.langs = ['en']
            tdoc.translations['en'] = {}
            tdoc.save()

        return tdoc


def get_language_list(domain):
    tdoc = get_or_create_translation_doc(domain)
    result = set(tdoc.langs)
    result.discard('*')
    return list(result)
