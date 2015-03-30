from collections import defaultdict
import re
import json
from dateutil.parser import parse
from datetime import datetime, timedelta
from decimal import Decimal
from couchdbkit.ext.django.schema import *
from couchdbkit.exceptions import MultipleResultsFound
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from dimagi.utils.couch.database import get_safe_write_kwargs
from dimagi.utils.modules import try_import
from dimagi.utils.parsing import json_format_datetime
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
        from corehq.apps.sms.util import strip_plus
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
    display_name = StringProperty()        # Simple name to display to users - e.g. Twilio
    authorized_domains = ListProperty(StringProperty)  # A list of additional domains that are allowed to use this backend
    is_global = BooleanProperty(default=True)  # If True, this backend can be used for any domain
    description = StringProperty()          # (optional) A description of this backend
    # A list of countries that this backend supports.
    # This information is displayed in the gateway list UI.
    # If this this backend represents an international gateway,
    # set this to: ['*']
    supported_countries = ListProperty(StringProperty)
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

class SMSLoadBalancingInfo(object):
    def __init__(self, phone_number, stats_key=None, stats=None,
        redis_client=None, lock=None):
        self.phone_number = phone_number
        self.stats_key = stats_key
        self.stats = stats
        self.redis_client = redis_client
        self.lock = lock

    def finish(self, save_stats=True, raise_exc=False):
        try:
            if (save_stats and self.stats_key and self.stats and
                self.redis_client):
                dumpable = {}
                for k, v in self.stats.items():
                    dumpable[k] = [json_format_datetime(t) for t in v]
                self.redis_client.set(self.stats_key, json.dumps(dumpable))
            if self.lock:
                self.lock.release()
        except:
            if raise_exc:
                raise

class SMSLoadBalancingMixin(Document):
    """
    A mixin to be used with an instance of SMSBackend. When using this you will
    need to:
    1) implement get_load_balancing_interval()
    2) optionally, override the phone_numbers property if necessary
    3) have the send() method expect an orig_phone_number kwarg, which will
       be the phone number to send from. This parameter is always sent in for
       instances of SMSLoadBalancingMixin, even if there's just one phone number
       in self.phone_numbers.
    4) have the backend's form class use the LoadBalancingBackendFormMixin to
       automatically set the load balancing phone numbers.
    """
    # Do not access this property directly as subclasses may override the
    # method below.
    x_phone_numbers = ListProperty(StringProperty)

    @property
    def phone_numbers(self):
        """
        Defined as a property here so that subclasses can override if
        necessary.
        """
        return self.x_phone_numbers

    def get_load_balancing_interval(self):
        """
        Defines the interval, in seconds, over which to load balance. For
        example, if this returns 60, it means that it will consider sms sent
        in the last 60 seconds from all phone numbers in order to choose the
        next phone number to use.
        """
        raise NotImplementedError("Please implement this method.")

    def _get_next_phone_number(self, redis_client):
        """
        Gets the least-used phone number from self.phone_numbers in the last
        n seconds, where n = self.get_load_balancing_interval().

        Returns an SMSLoadBalancingInfo object, which has the phone number to
        use. Since that phone number may end up not being used due to other
        conditions (such as rate limiting), you must call the .finish() method
        on this info object when you're done, sending save_stats=True if you
        ended up using the phone number, or False if not.
        """
        lock_key = "sms-load-balancing-lock-%s" % self._id
        lock = redis_client.lock(lock_key, timeout=30)
        lock.acquire()

        try:
            start_timestamp = (datetime.utcnow() -
                timedelta(seconds=self.get_load_balancing_interval()))

            stats_key = "sms-load-balancing-stats-%s" % self._id
            stats = redis_client.get(stats_key)

            # The stats entry looks like {phone_number: [list of timestamps]}
            # for each phone number, showing the list of timestamps that an
            # sms was sent using that phone number. Below, we validate the stats
            # entry and also clean it up to only include timestamps pertinent
            # to load balancing right now.
            try:
                assert stats is not None
                stats = json.loads(stats)
                assert isinstance(stats, dict)

                stats = {k: v for k, v in stats.items() if k in self.phone_numbers}
                new_stats = {}
                for k in stats:
                    v = stats[k]
                    assert isinstance(v, list)
                    new_v = []
                    for t in v:
                        try:
                            new_t = parse(t).replace(tzinfo=None)
                        except:
                            new_t = None
                        if isinstance(new_t, datetime) and new_t > start_timestamp:
                            new_v.append(new_t)
                    new_stats[k] = new_v
                stats = new_stats

                for k in self.phone_numbers:
                    if k not in stats:
                        stats[k] = []
            except:
                stats = {k: [] for k in self.phone_numbers}

            # Now that the stats entry is good, we choose the phone number that
            # has been used the least amount.
            phone_number = self.phone_numbers[0]
            num_sms_sent = len(stats[phone_number])
            for k in self.phone_numbers:
                if len(stats[k]) < num_sms_sent:
                    num_sms_sent = len(stats[k])
                    phone_number = k

            # Add the current timestamp for the chosen number
            stats[phone_number].append(datetime.utcnow())

            return SMSLoadBalancingInfo(phone_number, stats_key, stats,
                redis_client, lock)

        except:
            # If an exception occurs, we need to make sure the lock is released.
            # However, if no exception occurs, we don't release the lock since
            # it must be released by calling the .finish() method on the return
            # value.
            lock.release()
            raise

    def get_next_phone_number(self, redis_client, raise_exc=False):
        try:
            info = self._get_next_phone_number(redis_client)
        except:
            if raise_exc:
                raise
            info = SMSLoadBalancingInfo(self.phone_numbers[0])
        return info

class SMSBackend(MobileBackend):
    backend_type = "SMS"

    def get_sms_interval(self):
        """
        Override to use rate limiting. Return None to not use rate limiting,
        otherwise return the number of seconds by which outbound sms requests
        should be separated when using this backend.
        Note that this should not be over 30 due to choice of redis lock 
        timeout. See corehq.apps.sms.tasks.handle_outgoing.

        Also, this can be a fractional amount of seconds. For example, to
        separate requests by a minimum of a quarter second, return 0.25.
        """
        return None

    def send(msg, *args, **kwargs):
        raise NotImplementedError("send() method not implemented")

    @classmethod
    def get_opt_in_keywords(cls):
        """
        Override to specify a set of opt-in keywords to use for this
        backend type.
        """
        return []

    @classmethod
    def get_opt_out_keywords(cls):
        """
        Override to specify a set of opt-out keywords to use for this
        backend type.
        """
        return []

    @classmethod
    def get_wrapped(cls, backend_id):
        from corehq.apps.sms.util import get_available_backends
        backend_classes = get_available_backends()
        try:
            backend = SMSBackend.get(backend_id)
        except ResourceNotFound:
            raise UnrecognizedBackendException("Backend %s not found" %
                backend_id)
        doc_type = backend.doc_type
        if doc_type in backend_classes:
            backend = backend_classes[doc_type].wrap(backend.to_json())
            return backend
        else:
            raise UnrecognizedBackendException("Backend %s has an "
                "unrecognized doc type." % backend_id)


class BackendMapping(Document):
    domain = StringProperty()
    is_global = BooleanProperty()
    prefix = StringProperty()
    backend_id = StringProperty() # Couch Document id of a MobileBackend

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
        chars = re.compile(r"(\s|-|\.)+")
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

    def get_verified_numbers(self, include_pending=False):
        v = VerifiedNumber.view("sms/verified_number_by_owner_id",
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
        v = VerifiedNumber.view("sms/verified_number_by_number",
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
