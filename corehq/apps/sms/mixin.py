from collections import defaultdict
import re
from couchdbkit.ext.django.schema import *
from couchdbkit.exceptions import MultipleResultsFound
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

class BadSMSConfigException(Exception):
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
        from corehq.apps.sms.util import clean_phone_number
        if self.backend_id is not None and isinstance(self.backend_id, basestring) and self.backend_id.strip() != "":
            return MobileBackend.load_by_name(self.domain, self.backend_id)
        else:
            return MobileBackend.auto_load(clean_phone_number(self.phone_number), self.domain)

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
        elif self.owner_doc_type == "CommTrackUser":
            # Circular import
            from corehq.apps.commtrack.models import CommTrackUser
            return CommTrackUser.get(self.owner_id)
        elif self.owner_doc_type == 'WebUser':
            # Circular importsms
            from corehq.apps.users.models import WebUser
            return WebUser.get(self.owner_id)
        else:
            return None

    def retire(self, deletion_id=None):
        self.doc_type += DELETED_SUFFIX
        if deletion_id:
            self['-deletion_id'] = deletion_id

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
            "sms/verified_number_by_number",
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
                "sms/verified_number_by_suffix",
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
                     key=strip_plus(phone_number),
                     include_docs=True).one()
        return v if (include_pending or (v and v.verified)) else None

    @classmethod
    def by_domain(cls, domain):
        result = cls.view("sms/verified_number_by_domain",
                          startkey=[domain],
                          endkey=[domain, {}],
                          include_docs=True,
                          reduce=False).all()
        return result

def strip_plus(phone_number):
    return phone_number[1:] if phone_number.startswith('+') else phone_number

def add_plus(phone_number):
    return ('+' + phone_number) if not phone_number.startswith('+') else phone_number

def get_global_prefix_backend_mapping():
    result = {}
    for entry in BackendMapping.view("sms/backend_map", startkey=["*"], endkey=["*", {}], include_docs=True).all():
        if entry.prefix == "*":
            result[""] = entry.backend_id
        else:
            result[entry.prefix] = entry.backend_id
    return result

class MobileBackend(Document):
    """
    Defines an instance of a backend api to be used for either sending sms, or sending outbound calls.
    """
    class Meta:
        app_label = "sms"

    base_doc = "MobileBackend"
    domain = StringProperty()               # This is the domain that the backend belongs to, or None for global backends
    name = StringProperty()                 # The name to use when setting this backend for a contact
    authorized_domains = ListProperty(StringProperty)  # A list of additional domains that are allowed to use this backend
    is_global = BooleanProperty(default=True)  # If True, this backend can be used for any domain
    description = StringProperty()          # (optional) A description of this backend
    # TODO: Once the ivr backends get refactored, can remove these two properties:
    outbound_module = StringProperty()      # The fully-qualified name of the outbound module to be used (sms backends: must implement send(); ivr backends: must implement initiate_outbound_call() )
    outbound_params = DictProperty()        # The parameters which will be the keyword arguments sent to the outbound module's send() method
    reply_to_phone_number = StringProperty() # The phone number which you can text to / call to reply to this backend

    def domain_is_authorized(self, domain):
        return self.is_global or domain == self.domain or domain in self.authorized_domains

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
        global_backends = get_global_prefix_backend_mapping()
        backend_mapping = sorted(global_backends.iteritems(),
                                 key=lambda (prefix, backend): len(prefix),
                                 reverse=True)
        for prefix, backend_id in backend_mapping:
            if phone_number.startswith('+' + prefix):
                return cls.load(backend_id)
        raise BadSMSConfigException('no suitable backend found for phone number %s' % phone_number)

    @classmethod
    def load(cls, backend_id):
        """load a mobile backend
            backend_id  - the Couch document _id of the backend to load
        """
        # Circular import
        from corehq.apps.sms.util import get_available_backends
        backend_classes = get_available_backends()
        backend = cls.get(backend_id)
        if backend.doc_type not in backend_classes:
            raise Exception("Unexpected backend doc_type found '%s' for backend '%s'" % (backend.doc_type, backend._id))
        else:
            return backend_classes[backend.doc_type].wrap(backend.to_json())

    @classmethod
    def load_by_name(cls, domain, name):
        """
        Attempts to load the backend with the given name.
        If no matching backend is found, a RuntimeError is raised.
        """
        # First look for backends with that name that are owned by domain
        name = name.strip().upper()
        backend = cls.view("sms/backend_by_owner_domain", key=[domain, name], include_docs=True).one()
        if backend is None:
            # Look for a backend with that name that this domain was granted access to
            backend = cls.view("sms/backend_by_domain", key=[domain, name], include_docs=True, reduce=False).first()
            if backend is None:
                # Look for a global backend with that name
                backend = cls.view(
                    "sms/global_backends",
                    key=[name],
                    include_docs=True,
                    reduce=False
                ).one()
        if backend is not None:
            return cls.load(backend._id)
        else:
            raise BadSMSConfigException("Could not find backend '%s' from domain '%s'" % (name, domain))

    @classmethod
    def get_api_id(cls):
        """
        This method should return the backend's api id.
        TODO: We can probably remove this method if everything is switched to check what subclass of MobileBackend is being used.
        """
        raise NotImplementedError("Please define get_api_id()")

    @classmethod
    def get_generic_name(cls):
        """
        This method should return a descriptive name for this backend (such as "Unicel" or "Tropo"), for use in identifying it to an end user.
        """
        raise NotImplementedError("Please define get_generic_name()")

    @classmethod
    def get_template(cls):
        """
        This method should return the path to the Django template which will be used to capture values for this backend's specific properties.
        This template should extend sms/add_backend.html
        """
        return "sms/add_backend.html"

    @classmethod
    def get_form_class(cls):
        """
        This method should return a subclass of corehq.apps.sms.forms.BackendForm
        """
        raise NotImplementedError("Please define get_form_class()")

    @property
    def backend_module(self):
        module = try_import(self.outbound_module)
        if not module:
            raise RuntimeError('could not find outbound module %s' % self.outbound_module)
        return module

    def retire(self):
        self.base_doc += "-Deleted"
        self.save()

    def get_cleaned_outbound_params(self):
        # for passing to functions, ensure the keys are all strings
        return dict((str(k), v) for k, v in self.outbound_params.items())

class SMSBackend(MobileBackend):
    backend_type = "SMS"

    def send(msg, *args, **kwargs):
        raise NotImplementedError("send() method not implemented")

class BackendMapping(Document):
    domain = StringProperty()
    is_global = BooleanProperty()
    prefix = StringProperty()
    backend_id = StringProperty() # Couch Document id of a MobileBackend

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

        return  The VerifiedNumber
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
