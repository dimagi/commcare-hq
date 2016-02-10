from collections import defaultdict
import re
import json
from dateutil.parser import parse
from datetime import datetime, timedelta
from decimal import Decimal
from dimagi.ext.couchdbkit import *
from couchdbkit.exceptions import MultipleResultsFound
from dimagi.utils.couch import release_lock
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from dimagi.utils.couch.database import get_safe_write_kwargs
from dimagi.utils.modules import try_import
from dimagi.utils.parsing import json_format_datetime
from django.db import transaction
from corehq.apps.domain.models import Domain
from couchdbkit import ResourceNotFound


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
    
    def __repr__(self):
        return '{phone} in {domain} (owned by {owner})'.format(
            phone=self.phone_number, domain=self.domain,
            owner=self.owner_id
        )

    @property
    def backend(self):
        from corehq.apps.sms.models import SQLMobileBackend
        from corehq.apps.sms.util import clean_phone_number
        if isinstance(self.backend_id, basestring) and self.backend_id.strip() != '':
            return SQLMobileBackend.load_by_name(
                SQLMobileBackend.SMS,
                self.domain,
                self.backend_id
            )
        else:
            return SQLMobileBackend.load_default_by_phone_and_domain(
                SQLMobileBackend.SMS,
                clean_phone_number(self.phone_number),
                domain=self.domain
            )

    @property
    def owner(self):
        if self.owner_doc_type == "CommCareCase":
            # Circular import
            from corehq.apps.sms.models import CommConnectCase
            return CommConnectCase.get(self.owner_id)
        elif self.owner_doc_type == "CommCareUser":
            # Circular import
            from corehq.apps.users.models import CommCareUser
            return CommCareUser.get(self.owner_id)
        elif self.owner_doc_type == 'WebUser':
            # Circular importsms
            from corehq.apps.users.models import WebUser
            return WebUser.get(self.owner_id)
        else:
            return None

    def retire(self, deletion_id=None, deletion_date=None):
        self.doc_type += DELETED_SUFFIX
        self['-deletion_id'] = deletion_id
        self['-deletion_date'] = deletion_date
        self.save()

    @classmethod
    def by_extensive_search(cls, phone_number):
        # Try to look up the verified number entry directly
        v = cls.by_phone(phone_number)

        # If not found, try to see if any number in the database is a substring
        # of the number given to us. This can happen if the telco prepends some
        # international digits, such as 011...
        if v is None:
            v = cls.by_phone(phone_number[1:])
        if v is None:
            v = cls.by_phone(phone_number[2:])
        if v is None:
            v = cls.by_phone(phone_number[3:])

        # If still not found, try to match only the last digits of numbers in 
        # the database. This can happen if the telco removes the country code
        # in the caller id.
        if v is None:
            v = cls.by_suffix(phone_number)

        return v

    @classmethod
    def by_phone(cls, phone_number, include_pending=False):
        return cls.phone_lookup(
            "phone_numbers/verified_number_by_number",
            phone_number,
            include_pending
        )

    @classmethod
    def by_suffix(cls, phone_number, include_pending=False):
        """
        Used to lookup a VerifiedNumber, trying to exclude country code digits.
        """
        try:
            result = cls.phone_lookup(
                "phone_numbers/verified_number_by_suffix",
                phone_number,
                include_pending
            )
        except MultipleResultsFound:
            # We can't pinpoint who the number belongs to because more than one
            # suffix matches. So treat it as if the result was not found.
            result = None
        return result

    @classmethod
    def phone_lookup(cls, view_name, phone_number, include_pending=False):
        # We use .one() here because the framework prevents duplicates
        # from being entered when a contact saves a number.
        # See CommCareMobileContactMixin.save_verified_number()
        v = cls.view(view_name,
                     key=apply_leniency(phone_number),
                     include_docs=True).one()
        return v if (include_pending or (v and v.verified)) else None

    @classmethod
    def by_domain(cls, domain, ids_only=False):
        result = cls.view("phone_numbers/verified_number_by_domain",
                          startkey=[domain],
                          endkey=[domain, {}],
                          include_docs=(not ids_only),
                          reduce=False).all()
        if ids_only:
            return [row['id'] for row in result]
        else:
            return result

    @classmethod
    def count_by_domain(cls, domain):
        result = cls.view("phone_numbers/verified_number_by_domain",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=False,
            reduce=True).all()
        if result:
            return result[0]['value']
        return 0


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
        v = VerifiedNumber.view("phone_numbers/verified_number_by_owner_id",
            key=self._id,
            include_docs=True
        )
        v = filter(lambda c: c.verified or include_pending, v)
        return dict((c.phone_number, c) for c in v)

    def get_verified_number(self, phone=None):
        """
        Retrieves this contact's verified number entry by (self.doc_type, self._id).

        return  the VerifiedNumber entry
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
        self.validate_number_format(phone_number)
        v = VerifiedNumber.view("phone_numbers/verified_number_by_number",
            key=phone_number,
            include_docs=True
        ).one()
        if v is not None and (v.owner_doc_type != self.doc_type or v.owner_id != self._id):
            raise PhoneNumberInUseException("Phone number is already in use.")

    def save_verified_number(self, domain, phone_number, verified, backend_id=None, ivr_backend_id=None, only_one_number_allowed=False):
        """
        Saves the given phone number as this contact's verified phone number.

        backend_id - the name of an SMSBackend to use when sending SMS to
            this number; if specified, this will override any project or
            global settings for which backend will be used to send sms to
            this number

        return  The VerifiedNumber
        raises  InvalidFormatException if the phone number format is invalid
        raises  PhoneNumberInUseException if the phone number is already in use by another contact
        """
        phone_number = apply_leniency(phone_number)
        self.verify_unique_number(phone_number)
        if only_one_number_allowed:
            v = self.get_verified_number()
        else:
            v = self.get_verified_number(phone_number)
        if v is None:
            v = VerifiedNumber(
                owner_doc_type = self.doc_type,
                owner_id = self._id
            )
        v.domain = domain
        v.phone_number = phone_number
        v.verified = verified
        v.backend_id = backend_id
        v.ivr_backend_id = ivr_backend_id
        v.save(**get_safe_write_kwargs())
        return v

    def delete_verified_number(self, phone_number=None):
        """
        Deletes this contact's phone number from the verified phone number list, freeing it up
        for use by other contacts.

        return  void
        """
        v = self.get_verified_number(phone_number)
        if v is not None:
            v.retire()
