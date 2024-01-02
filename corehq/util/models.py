import datetime
from collections import namedtuple
from functools import lru_cache

from django.contrib.postgres.fields import ArrayField
from django.utils.functional import cached_property
from django.db import models

from jsonfield import JSONField as jsonfield_JSONField

from dimagi.utils.logging import notify_exception
from corehq.toggles import BLOCKED_EMAIL_DOMAIN_RECIPIENTS
from corehq.util.metrics import metrics_counter

AwsMeta = namedtuple('AwsMeta', 'notification_type main_type sub_type '
                                'email reason headers timestamp '
                                'destination')


class NotificationType(object):
    BOUNCE = "Bounce"
    COMPLAINT = "Complaint"
    UNDETERMINED = "Undetermined"


class BounceType(object):
    PERMANENT = "Permanent"
    UNDETERMINED = "Undetermined"
    TRANSIENT = "Transient"  # todo handle these


class BounceSubType(object):
    """
    This is part of the information AWS SES uses to classify a bounce. Most
    crucial in limiting are the "Suppressed" emails, which have bounced on ANY
    AWS SES client's list within the past 14 days.
    """
    GENERAL = "General"
    SUPPRESSED = "Suppressed"
    UNDETERMINED = "Undetermined"
    CHOICES = (
        (GENERAL, GENERAL),
        (SUPPRESSED, SUPPRESSED),
        (UNDETERMINED, UNDETERMINED),
    )


# The number of non supressed or undetermined bounces
# we accept before hard rejecting an email
BOUNCE_EVENT_THRESHOLD = 3

HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE = 24

# Prior to this date we do not have reliable SNS metadata for emails.
# In order to get rid of this, we'll want to slowly roll the date back and
# let the emails re-bounce while keeping an eye on the bounce rate. Once we're
# confident the rate is stable, continue rolling back until Jan 1st 2020 and then
# this date requirement can be removed. The slow rollback is to avoid having a sudden
# jump in email bounces from the initial bounces we had cut off in the beginning.
LEGACY_BOUNCE_MANAGER_DATE = datetime.datetime(2020, 2, 10)


class BouncedEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True, unique=True)

    @classmethod
    def is_email_over_limits(cls, email):
        """
        Determines if an email has passed bounce event limits for general
        and transient bounces
        :param email: string
        :return: boolean
        """
        transient_bounce_query = TransientBounceEmail.get_active_query().filter(
            email=email,
        )
        general_bounce_query = PermanentBounceMeta.objects.filter(
            bounced_email__email=email,
            sub_type=BounceSubType.GENERAL,
        )
        return (
            transient_bounce_query.count() + general_bounce_query.count() > BOUNCE_EVENT_THRESHOLD
        )

    @staticmethod
    def is_bad_email_format(email_address):
        """
        This is a very rudimentary check to see that an email is formatted
        properly. It's not doing anything intelligent--like whether a TLD looks
        correct or that the domain name might be misspelled (gamil vs gmail).
        For the future, we might consider using something like Twilio's SendGrid.
        Ideally, any email validation should happen at the UI level rather
        than here, so that proper feedback can be given to the user.
        This is just a fail-safe so that we stop sending to foobar@gmail
        :param email_address:
        :return: boolean (True if email is poorly formatted)
        """
        try:
            if len(email_address.split('@')[1].split('.')) < 2:
                # if no TLD was present
                return True
        except IndexError:
            # if @ was missing
            return True
        return False

    @classmethod
    def get_hard_bounced_emails(cls, list_of_emails):
        # these are any Bounced Email Records we have
        bad_emails = set()

        for email_address in list_of_emails:
            if (BLOCKED_EMAIL_DOMAIN_RECIPIENTS.enabled(email_address)
                    or cls.is_bad_email_format(email_address)):
                bad_emails.add(email_address)

        list_of_emails = set(list_of_emails).difference(bad_emails)

        if len(list_of_emails) == 0:
            # don't query the db if we don't have to
            return bad_emails

        bounced_emails = set(
            BouncedEmail.objects.filter(email__in=list_of_emails).values_list(
                'email', flat=True
            )
        )

        transient_emails = set(
            TransientBounceEmail.get_active_query().filter(
                email__in=list_of_emails,
            ).values_list(
                'email', flat=True
            )
        )
        bounced_emails.update(transient_emails)

        # These are emails that were marked as Suppressed or Undetermined
        # by SNS metadata, meaning they definitely hard bounced
        permanent_bounces = set(
            PermanentBounceMeta.objects.filter(sub_type__in=[
                BounceSubType.UNDETERMINED, BounceSubType.SUPPRESSED
            ], bounced_email__email__in=bounced_emails).values_list(
                'bounced_email__email', flat=True)
        )
        bad_emails.update(permanent_bounces)

        # These are definite complaints against us
        complaints = set(
            ComplaintBounceMeta.objects.filter(
                bounced_email__email__in=bounced_emails.difference(bad_emails)
            ).values_list('bounced_email__email', flat=True)
        )
        bad_emails.update(complaints)

        # see note surrounding LEGACY_BOUNCE_MANAGER_DATE above
        legacy_bounced_emails = set(
            BouncedEmail.objects.filter(
                email__in=list_of_emails,
                created__lte=LEGACY_BOUNCE_MANAGER_DATE,
            ).values_list(
                'email', flat=True
            )
        )
        bad_emails.update(legacy_bounced_emails)

        for remaining_email in bounced_emails.difference(bad_emails):
            if cls.is_email_over_limits(remaining_email):
                bad_emails.add(remaining_email)

        from corehq.util.email_event_utils import get_emails_to_never_bounce
        return bad_emails.difference(get_emails_to_never_bounce())


class TransientBounceEmail(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    email = models.EmailField(db_index=True)
    timestamp = models.DateTimeField(db_index=True)
    headers = models.JSONField(blank=True, null=True)

    @classmethod
    def get_expired_query(cls):
        return cls.objects.filter(
            created__lt=datetime.datetime.utcnow() - datetime.timedelta(
                hours=HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE + 1
            )
        )

    @classmethod
    def delete_expired_bounces(cls):
        cls.get_expired_query().delete()

    @classmethod
    def get_active_query(cls):
        return cls.objects.filter(
            created__gte=datetime.datetime.utcnow() - datetime.timedelta(
                hours=HOURS_UNTIL_TRANSIENT_BOUNCES_EXPIRE)
        )


class PermanentBounceMeta(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    bounced_email = models.ForeignKey(BouncedEmail, on_delete=models.PROTECT)
    timestamp = models.DateTimeField()
    sub_type = models.CharField(
        max_length=20,
        choices=BounceSubType.CHOICES
    )
    headers = models.JSONField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    destination = ArrayField(models.EmailField(), default=list, blank=True, null=True)


class ComplaintBounceMeta(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    bounced_email = models.ForeignKey(BouncedEmail, on_delete=models.PROTECT)
    timestamp = models.DateTimeField()
    headers = models.JSONField(blank=True, null=True)
    feedback_type = models.CharField(max_length=50, blank=True, null=True)
    sub_type = models.CharField(max_length=50, blank=True, null=True)
    destination = ArrayField(models.EmailField(), default=list, blank=True, null=True)


class NullJsonField(jsonfield_JSONField):
    """A JSONField that stores null when its value is empty

    Any value stored in this field will be discarded and replaced with
    the default if it evaluates to false during serialization.
    """

    def __init__(self, **kw):
        kw.setdefault("null", True)
        super().__init__(**kw)
        assert self.null

    def get_db_prep_value(self, value, *args, **kw):
        if not value:
            value = None
        return super().get_db_prep_value(value, *args, **kw)

    def to_python(self, value):
        value = super().to_python(value)
        return self.get_default() if value is None else value

    def from_db_value(self, value, expression, connection):
        value = super().from_db_value(value, expression, connection)
        return self.get_default() if value is None else value

    def pre_init(self, value, obj):
        value = super().pre_init(value, obj)
        return self.get_default() if value is None else value


class TruncatingCharField(models.CharField):
    """
    http://stackoverflow.com/a/3460942
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value:
            return value[:self.max_length]
        return value


class ForeignObject:
    """Property descriptor for objects that live in a different database

    This is useful for cases where a related object lives in a separate
    database where a ForeignKey reference is not possible. The object
    may be referenced as a simple attribute, just like a ForeignKey.
    """

    def __init__(self, id_field, get_by_id):
        self.id_field = id_field
        self.get_by_id = get_by_id

    def __set_name__(self, owner, name):
        assert not hasattr(self, "name"), (self.name, owner, name)
        self.name = name
        other_names = getattr(owner, "_Foreign_names", [])
        owner._Foreign_names = other_names + [name]

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        fobj_id = getattr(obj, self.id_field.name)
        try:
            fobj = getattr(obj, f"_ForeignObject_{self.name}")
            if fobj_id is None or fobj is not None and fobj.id != fobj_id:
                raise AttributeError
        except AttributeError:
            fobj = self.get_by_id(obj, fobj_id)
            setattr(obj, f"_ForeignObject_{self.name}", fobj)
        return fobj

    def __set__(self, obj, value):
        if value is None:
            if getattr(obj, self.id_field.name) is not None:
                self.__delete__(obj)
            return
        setattr(obj, self.id_field.name, value.id)
        setattr(obj, f"_ForeignObject_{self.name}", value)

    def __delete__(self, obj):
        setattr(obj, self.id_field.name, None)
        delattr(obj, f"_ForeignObject_{self.name}")

    @staticmethod
    def get_names(cls):
        """Get a list of foreign attribute names of the given class

        Raises `AttributeError` if the class has no `ForeignValue` attributes.
        """
        return cls._Foreign_names


class ForeignValue(ForeignObject):
    """Property descriptor for Django foreign key refs with a primitive value

    This is useful for cases where the object referenced by the foreign
    key holds a single primitive value named `value`. It eliminates
    boilerplate indirection imposed by the foreign key, allowing the
    value to be referenced as a simple attribute. This pattern is used
    to save space when the set of values is relatively small while each
    value is much larger than a (usually integer) foreign key.

    An LRU cache is used to keep recently fetched related objects in
    memory rather than fetching from the database each time a new value
    is set or fetched. Pass `cache_size=0` disable the LRU-cache. Note that the
    `__set__` and `__get__` use different caches (each of the same size).

    Note: corehq.util.test_utils.patch_foreign_value_caches for how the caches
    are cleared in tests.
    """

    def __init__(self, foreign_key: models.ForeignKey, truncate=False, cache_size=1000):
        self.fk = foreign_key
        self.truncate = truncate
        self.cache_size = cache_size

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        fobj_id = getattr(obj, f"{self.fk.name}_id")
        if fobj_id is None:
            fobj = getattr(obj, self.fk.name)
            return fobj.value if fobj is not None else None
        return self.get_value(fobj_id)

    @cached_property
    def get_value(self):
        def get_value(fk_id):
            try:
                metrics_counter(
                    "commcare.foreignvalue.get_value.cachemiss",
                    tags={"key": self.fk_path},
                )
                return manager.filter(pk=fk_id).values_list('value', flat=True)[0]
            except IndexError:
                return None
        manager = self.fk.related_model.objects
        if self.cache_size:
            get_value = lru_cache(self.cache_size)(get_value)
        return get_value

    def __set__(self, obj, value):
        if value is None:
            if getattr(obj, self.fk.name) is not None:
                setattr(obj, self.fk.name, None)
            return
        if self.truncate:
            value = value[:self.max_length]
        fobj = self.get_related(value)
        setattr(obj, self.fk.name, fobj)

    @cached_property
    def max_length(self):
        return self.fk.related_model._meta.get_field("value").max_length

    @cached_property
    def get_related(self):
        def get_related(value):
            try:
                metrics_counter(
                    "commcare.foreignvalue.get_related.cachemiss",
                    tags={"key": self.fk_path},
                )
                return manager.get_or_create(value=value)[0]
            except model.MultipleObjectsReturned:
                notify_exception(None, f"{model} multiple objects returned. "
                    "Does your 'value' field have a unique constraint?")
                return manager.filter(value=value).order_by("id").first()
        model = self.fk.related_model
        manager = self.fk.related_model.objects
        if self.cache_size:
            get_related = lru_cache(self.cache_size)(get_related)
        return get_related

    @cached_property
    def fk_path(self):
        meta = self.fk.model._meta
        return f"{meta.app_label}.{meta.object_name}.{self.fk.name}"


def foreign_init(cls):
    """Class decorator that adds a ForeignValue-compatible __init__ method

    Use this on classes with `ForeignValue` attributes that want to
    accept values for those attributes passed to their constructor.
    """
    def __init__(self, *args, **kw):
        values = {n: kw.pop(n) for n in names if n in kw}
        super_init(self, *args, **kw)
        for name, value in values.items():
            setattr(self, name, value)

    names = ForeignValue.get_names(cls)
    super_init = cls.__init__
    cls.__init__ = __init__
    return cls
