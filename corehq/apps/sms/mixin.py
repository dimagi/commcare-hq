import re
from couchdbkit.ext.django.schema import *
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from dimagi.utils.couch.database import get_safe_write_kwargs
from dimagi.utils.modules import try_import
from corehq.apps.domain.models import Domain

phone_number_re = re.compile("^\d+$")

class PhoneNumberException(Exception):
    pass

class InvalidFormatException(PhoneNumberException):
    pass

class PhoneNumberInUseException(PhoneNumberException):
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
    backend_id      = StringProperty() # points to a MobileBackend
    ivr_backend_id  = StringProperty() # points to a MobileBackend
    verified        = BooleanProperty()
    
    def __repr__(self):
        return '{phone} in {domain} (owned by {owner})'.format(
            phone=self.phone_number, domain=self.domain,
            owner=self.owner_id
        )

    @property
    def backend(self):
        if self.backend_id is None or self.backend_id == "":
            return MobileBackend.auto_load("+%s" % self.phone_number, self.domain)
        else:
            return MobileBackend.load(self.backend_id)
    
    @property
    def ivr_backend(self):
        return MobileBackend.get(self.ivr_backend_id)
    
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
        else:
            return None

    def retire(self, deletion_id=None):
        self.doc_type += DELETED_SUFFIX
        if deletion_id:
            self['-deletion_id'] = deletion_id

        self.save()
    
    @classmethod
    def by_phone(cls, phone_number, include_pending=False):
        # TODO: do we assume phone number duplicates are prevented?
        v = cls.view("sms/verified_number_by_number",
                     key=strip_plus(phone_number),
                     include_docs=True).one()
        return v if (include_pending or (v and v.verified)) else None

def strip_plus(phone_number):
    return phone_number[1:] if phone_number.startswith('+') else phone_number

def add_plus(phone_number):
    return ('+' + phone_number) if not phone_number.startswith('+') else phone_number

class MobileBackend(Document):
    """
    Defines an instance of a backend api to be used for either sending sms, or sending outbound calls.
    """
    domain = ListProperty(StringProperty)   # A list of domains for which this backend is applicable
    description = StringProperty()          # (optional) A description of this backend
    outbound_module = StringProperty()      # The fully-qualified name of the outbound module to be used (sms backends: must implement send(); ivr backends: must implement initiate_outbound_call() )
    outbound_params = DictProperty()        # The parameters which will be the keyword arguments sent to the outbound module's send() method

    @classmethod
    def auto_load(cls, phone_number, domain=None):
        """
        Get the appropriate outbound SMS backend to send to a
        particular phone_number
        """
        phone_number = add_plus(phone_number)

        # Use the domain-wide default backend if possible
        if domain is not None:
            domain_obj = Domain.get_by_name(domain, strict=True)
            if domain_obj.default_sms_backend_id is not None and domain_obj.default_sms_backend_id != "":
                return cls.load(domain_obj.default_sms_backend_id)
        
        # Use the appropriate system-wide default backend
        global_backends = getattr(settings, 'SMS_BACKENDS', {})
        backend_mapping = sorted(global_backends.iteritems(),
                                 key=lambda (prefix, backend): len(prefix),
                                 reverse=True)
        for prefix, backend in backend_mapping:
            if phone_number.startswith('+' + prefix):
                return cls.load(backend)
        raise RuntimeError('no suitable backend found for phone number %s' % phone_number)

    @classmethod
    def load(cls, backend_id):
        """load a mobile backend
        for 'old-style' backends, create a virtual backend record
        wrapping the backend module
        """
        # new-style backend
        try:
            return cls.get(backend_id)
        except:
            pass

        # old-style backend

        # hard-coded old-style backends with new-style IDs
        # once the backend migration is complete, these backends
        # should exist in couch
        transitional = {
            'MOBILE_BACKEND_MACH': 'corehq.apps.sms.mach_api',
            'MOBILE_BACKEND_UNICEL': 'corehq.apps.unicel.api',
            'MOBILE_BACKEND_TEST': 'corehq.apps.sms.test_backend',
            # tropo?
        }
        try:
            module = transitional[backend_id]
        except KeyError:
            module = backend_id

        return cls(
            _id=backend_id,
            outbound_module=module,
            description='virtual backend for %s' % backend_id,
        )

    @property
    def backend_module(self):
        module = try_import(self.outbound_module)
        if not module:
            raise RuntimeError('could not find outbound module %s' % self.outbound_module)
        return module

    def get_cleaned_outbound_params(self):
        # for passing to functions, ensure the keys are all strings
        return dict((str(k), v) for k, v in self.outbound_params.items())

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

    def get_verified_numbers(self, include_pending=False):
        v = VerifiedNumber.view("sms/verified_number_by_doc_type_id",
            startkey=[self.doc_type, self._id],
            endkey=[self.doc_type, self._id],
            include_docs=True
        )
        v = filter(lambda c: c.verified or include_pending, v)
        return dict((c.phone_number, c) for c in v)

    def get_verified_number(self, phone=None):
        """
        Retrieves this contact's verified number entry by (self.doc_type, self._id).

        return  the VerifiedNumber entry
        """
        verified = self.get_verified_numbers(True)
        if not phone:
            # for backwards compatibility with code that assumes only one verified phone #
            if len(verified) > 0:
                return sorted(verified.iteritems())[0][1]
            else:
                return None

        return verified.get(strip_plus(phone))

    def validate_number_format(self, phone_number):
        """
        Validates that the given phone number consists of all digits.

        return  void
        raises  InvalidFormatException if the phone number format is invalid
        """
        if not phone_number_re.match(phone_number):
            raise InvalidFormatException("Phone number format must consist of only digits.")

    def verify_unique_number(self, phone_number):
        """
        Verifies that the given phone number is not already in use by any other contacts.

        return  void
        raises  InvalidFormatException if the phone number format is invalid
        raises  PhoneNumberInUseException if the phone number is already in use by another contact
        """
        self.validate_number_format(phone_number)
        v = VerifiedNumber.view("sms/verified_number_by_number",
            key=phone_number,
            include_docs=True
        ).one()
        if v is not None and (v.owner_doc_type != self.doc_type or v.owner_id != self._id):
            raise PhoneNumberInUseException("Phone number is already in use.")

    def save_verified_number(self, domain, phone_number, verified, backend_id, ivr_backend_id=None, only_one_number_allowed=False):
        """
        Saves the given phone number as this contact's verified phone number.

        return  void
        raises  InvalidFormatException if the phone number format is invalid
        raises  PhoneNumberInUseException if the phone number is already in use by another contact
        """
        phone_number = strip_plus(phone_number)
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

    def delete_verified_number(self, phone_number=None):
        """
        Deletes this contact's phone number from the verified phone number list, freeing it up
        for use by other contacts.

        return  void
        """
        v = self.get_verified_number(phone_number)
        if v is not None:
            v.retire()
