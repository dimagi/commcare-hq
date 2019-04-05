from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.ext.couchdbkit import *
import re
from decimal import Decimal
from dimagi.utils.couch import CriticalSection
from collections import namedtuple
import six

from corehq.util.python_compatibility import soft_assert_type_text

phone_number_re = re.compile(r"^\d+$")


class PhoneNumberException(Exception):
    pass


class InvalidFormatException(PhoneNumberException):
    pass


class PhoneNumberInUseException(PhoneNumberException):
    pass


class BadSMSConfigException(Exception):
    pass


class BackendProcessingException(Exception):
    pass


class UnrecognizedBackendException(Exception):
    pass


class VerifiedNumber(Document):
    """
    There should only be one VerifiedNumber entry per (owner_doc_type, owner_id), and
    each VerifiedNumber.phone_number should be unique across all entries.
    """
    domain          = StringProperty()
    owner_doc_type  = StringProperty()
    owner_id        = StringProperty()
    phone_number    = StringProperty()
    backend_id      = StringProperty() # the name of a MobileBackend (can be domain-level or system-level)
    ivr_backend_id  = StringProperty() # points to a MobileBackend
    verified        = BooleanProperty()
    contact_last_modified = DateTimeProperty()


def add_plus(phone_number):
    return ('+' + phone_number) if not phone_number.startswith('+') else phone_number


def apply_leniency(contact_phone_number):
    """
    The documentation says that contact_phone_number should be
    in international format and consist of only digits. However,
    we can apply some leniency to avoid common mistakes.
    Returns None if an unsupported data type is passed in.
    """
    from corehq.apps.sms.util import strip_plus
    # Decimal preserves trailing zeroes, so it's ok 
    if isinstance(contact_phone_number, six.integer_types + (Decimal,)):
        contact_phone_number = six.text_type(contact_phone_number)
    if isinstance(contact_phone_number, six.string_types):
        soft_assert_type_text(contact_phone_number)
        chars = re.compile(r"[()\s\-.]+")
        contact_phone_number = chars.sub("", contact_phone_number)
        contact_phone_number = strip_plus(contact_phone_number)
    else:
        contact_phone_number = None
    return contact_phone_number


class CommCareMobileContactMixin(object):
    """
    Defines a mixin to manage a mobile contact's information. This mixin must be used with
    a class which is a Couch Document.
    """

    @property
    def phone_sync_key(self):
        return 'sync-contact-phone-numbers-for-%s' % self.get_id

    def get_time_zone(self):
        """
        This method should be implemented by all subclasses of CommCareMobileContactMixin,
        and must return a string representation of the time zone. For example, "America/New_York".
        """
        raise NotImplementedError("Subclasses of CommCareMobileContactMixin must implement method get_time_zone().")

    def get_language_code(self):
        """
        This method should be implemented by all subclasses of CommCareMobileContactMixin,
        and must return the preferred language code of the contact. For example, "en".
        """
        raise NotImplementedError("Subclasses of CommCareMobileContactMixin must implement method get_language_code().")

    def get_email(self):
        """
        This method should be implemented by all subclasses of
        CommCareMobileContactMixin and should return the contact's
        email address or None if it doesn't have one.
        """
        raise NotImplementedError('Please implement this method')

    def get_phone_entries(self):
        from corehq.apps.sms.models import PhoneNumber
        return {
            p.phone_number: p
            for p in PhoneNumber.by_owner_id(self.get_id)
        }

    def get_two_way_numbers(self):
        from corehq.apps.sms.models import PhoneNumber
        two_way_entries = [p for p in PhoneNumber.by_owner_id(self.get_id) if p.is_two_way]
        return {
            p.phone_number: p for p in two_way_entries
        }

    @classmethod
    def validate_number_format(cls, phone_number):
        """
        Validates that the given phone number consists of all digits.

        return  void
        raises  InvalidFormatException if the phone number format is invalid
        """
        if (not phone_number) or (not phone_number_re.match(phone_number)):
            raise InvalidFormatException("Phone number format must consist of only digits.")

    def _create_phone_entry(self, phone_number):
        from corehq.apps.sms.models import PhoneNumber
        return PhoneNumber.objects.create(
            domain=self.domain,
            owner_doc_type=self.doc_type,
            owner_id=self.get_id,
            phone_number=phone_number,
            verified=False,
            pending_verification=False,
            is_two_way=False
        )

    def create_phone_entry(self, phone_number):
        phone_number = apply_leniency(phone_number)
        self.validate_number_format(phone_number)
        return self._create_phone_entry(phone_number)

    def get_or_create_phone_entry(self, phone_number):
        with CriticalSection([self.phone_sync_key]):
            return self._get_or_create_phone_entry(phone_number)

    def _get_or_create_phone_entry(self, phone_number):
        phone_number = apply_leniency(phone_number)
        self.validate_number_format(phone_number)

        entries = self.get_phone_entries()
        if phone_number in entries:
            return entries[phone_number]

        return self._create_phone_entry(phone_number)

    def delete_phone_entry(self, phone_number):
        phone_number = apply_leniency(phone_number)
        entry = self.get_phone_entries().get(phone_number)
        if entry:
            entry.delete()


class MessagingCaseContactMixin(CommCareMobileContactMixin):

    def get_phone_info(self):
        PhoneInfo = namedtuple(
            'PhoneInfo',
            [
                'requires_entry',
                'qualifies_as_two_way',
                'phone_number',
                'sms_backend_id',
                'ivr_backend_id',
            ]
        )
        contact_phone_number = self.get_case_property('contact_phone_number')
        contact_phone_number = apply_leniency(contact_phone_number)
        contact_phone_number_is_verified = self.get_case_property('contact_phone_number_is_verified')
        contact_backend_id = self.get_case_property('contact_backend_id')
        contact_ivr_backend_id = self.get_case_property('contact_ivr_backend_id')

        try:
            self.validate_number_format(contact_phone_number)
        except InvalidFormatException:
            format_is_valid = False
        else:
            format_is_valid = True

        requires_entry = (
            contact_phone_number and
            format_is_valid and
            contact_phone_number != '0' and
            not self.closed and
            not self.is_deleted
        )

        qualifies_as_two_way = (
            requires_entry and
            # Avoid setting two-way numbers when only the country code was entered
            len(contact_phone_number) > 3 and
            # For legacy reasons, any truthy value here suffices
            contact_phone_number_is_verified
        )

        return PhoneInfo(
            requires_entry,
            qualifies_as_two_way,
            contact_phone_number,
            contact_backend_id,
            contact_ivr_backend_id
        )

    def get_time_zone(self):
        return self.get_case_property('time_zone')

    def get_language_code(self):
        return self.get_case_property('language_code')

    def get_email(self):
        return self.get_case_property('commcare_email_address')

    def get_phone_number(self):
        entries = self.get_phone_entries()
        if len(entries) == 0:
            return None

        return list(entries.values())[0]

    @property
    def raw_username(self):
        return self.name
