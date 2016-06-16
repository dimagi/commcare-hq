from dimagi.ext.couchdbkit import *
import re
from decimal import Decimal
from collections import namedtuple


phone_number_re = re.compile("^\d+$")


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
    if isinstance(contact_phone_number, (int, long, Decimal)):
        contact_phone_number = str(contact_phone_number)
    if isinstance(contact_phone_number, basestring):
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

    def get_verified_numbers(self, include_pending=False):
        from corehq.apps.sms.models import PhoneNumber
        v = PhoneNumber.by_owner_id(self.get_id)
        v = filter(lambda c: c.verified or include_pending, v)
        return dict((c.phone_number, c) for c in v)

    def get_verified_number(self, phone=None):
        """
        Retrieves this contact's verified number entry by (self.doc_type, self.get_id).

        return  the PhoneNumber entry
        """
        from corehq.apps.sms.util import strip_plus
        verified = self.get_verified_numbers(True)
        if not phone:
            # for backwards compatibility with code that assumes only one verified phone #
            if len(verified) > 0:
                return sorted(verified.iteritems())[0][1]
            else:
                return None

        return verified.get(strip_plus(phone))

    @classmethod
    def validate_number_format(cls, phone_number):
        """
        Validates that the given phone number consists of all digits.

        return  void
        raises  InvalidFormatException if the phone number format is invalid
        """
        if (not phone_number) or (not phone_number_re.match(phone_number)):
            raise InvalidFormatException("Phone number format must consist of only digits.")

    def verify_unique_number(self, phone_number):
        """
        Verifies that the given phone number is not already in use by any other contacts.

        return  void
        raises  InvalidFormatException if the phone number format is invalid
        raises  PhoneNumberInUseException if the phone number is already in use by another contact
        """
        from corehq.apps.sms.models import PhoneNumber
        self.validate_number_format(phone_number)
        v = PhoneNumber.by_phone(phone_number, include_pending=True)
        if v is not None and (v.owner_doc_type != self.doc_type or v.owner_id != self.get_id):
            raise PhoneNumberInUseException("Phone number is already in use.")

    def save_verified_number(self, domain, phone_number, verified, backend_id=None, ivr_backend_id=None, only_one_number_allowed=False):
        """
        Saves the given phone number as this contact's verified phone number.

        backend_id - the name of an SMSBackend to use when sending SMS to
            this number; if specified, this will override any project or
            global settings for which backend will be used to send sms to
            this number

        return  The PhoneNumber
        raises  InvalidFormatException if the phone number format is invalid
        raises  PhoneNumberInUseException if the phone number is already in use by another contact
        """
        from corehq.apps.sms.models import PhoneNumber

        phone_number = apply_leniency(phone_number)
        self.verify_unique_number(phone_number)
        if only_one_number_allowed:
            v = self.get_verified_number()
        else:
            v = self.get_verified_number(phone_number)
        if v is None:
            v = PhoneNumber(
                owner_doc_type=self.doc_type,
                owner_id=self.get_id
            )
        v.domain = domain
        v.phone_number = phone_number
        v.verified = verified
        v.backend_id = backend_id
        v.ivr_backend_id = ivr_backend_id
        v.save()

    def delete_verified_number(self, phone_number=None):
        """
        Deletes this contact's phone number from the verified phone number list, freeing it up
        for use by other contacts.

        return  void
        """
        v = self.get_verified_number(phone_number)
        if v is not None:
            v.delete()


class MessagingCaseContactMixin(CommCareMobileContactMixin):

    def get_phone_info(self):
        PhoneInfo = namedtuple(
            'PhoneInfo',
            [
                'requires_entry',
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

        requires_entry = (
            contact_phone_number and
            contact_phone_number != '0' and
            not self.closed and
            not self.is_deleted and
            # For legacy reasons, any truthy value here suffices
            contact_phone_number_is_verified
        )

        return PhoneInfo(
            requires_entry,
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

    @property
    def raw_username(self):
        return self.name
