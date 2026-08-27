from uuid import UUID, uuid4

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from casexml.apps.phone.models import OTARestoreUser
from dimagi.utils.web import get_url_base

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.util import PUBLIC_USER_ID


class PublicWebformType(models.TextChoices):
    REGISTRATION = ('registration', _("Registration"))
    SURVEY = ('survey', _("Survey"))


class PublicWebformStatus(models.IntegerChoices):
    """Whether a webform is accepting requests for a one-time link.

    Derived from ``expires_at`` and ``is_disabled`` rather than stored, so
    a webform expires without anything having to write to it.
    """

    OPEN = (0, _("Open"))
    CLOSED = (1, _("Closed"))
    EXPIRED = (2, _("Expired"))


class PublicWebformQuerySet(models.QuerySet):

    def with_status(self):
        """Annotate ``status``, so it can be filtered on in the database."""
        return self.annotate(
            status=models.Case(
                models.When(
                    expires_at__lt=timezone.now(),
                    then=models.Value(PublicWebformStatus.EXPIRED),
                ),
                models.When(
                    is_disabled=True,
                    then=models.Value(PublicWebformStatus.CLOSED),
                ),
                default=models.Value(PublicWebformStatus.OPEN),
                output_field=models.IntegerField(),
            ),
        )

    def with_submissions_count(self):
        return self.annotate(
            submissions=models.Count(
                'publicformsession',
                filter=models.Q(publicformsession__submitted_at__isnull=False),
            ),
        )


class PublicWebform(models.Model):

    public_id = models.UUIDField(default=uuid4, unique=True)
    label = models.CharField()
    domain = models.CharField()
    app_id = models.CharField()
    app_build_id = models.CharField()
    form_unique_id = models.CharField()
    endpoint_id = models.CharField()
    session_type = models.CharField(choices=PublicWebformType)
    allow_sms = models.BooleanField()
    allow_email = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_disabled = models.BooleanField(default=True)

    objects = PublicWebformQuerySet.as_manager()

    class Meta:
        indexes = [models.Index(fields=['domain', 'id'])]

    @property
    def public_url(self):
        """The absolute link a respondent opens to request a one-time link."""
        return f'{get_url_base()}/webforms/{self.public_id.hex}/'

    @property
    def is_expired(self):
        return self.expires_at < timezone.now()

    @property
    def is_open(self):
        return not self.is_disabled and not self.is_expired


class PublicFormSession(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid4)
    session_key = models.UUIDField(default=uuid4, unique=True, db_index=True)
    public_webform = models.ForeignKey(PublicWebform, on_delete=models.CASCADE, db_index=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    opened_at = models.DateTimeField(null=True)
    submitted_at = models.DateTimeField(null=True)
    xform_id = models.CharField(null=True)

    class Meta:
        indexes = [models.Index(fields=['public_webform', 'id'])]

    @classmethod
    def get_active_session_by_key(cls, session_key):
        """Return the usable (unsubmitted, unexpired) session for a raw
        session_key value, or None if the key is malformed or no such
        session is usable."""
        try:
            key = UUID(str(session_key))
        except (ValueError, TypeError):
            return None
        return cls.objects.filter(
            session_key=key,
            submitted_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).first()

    @property
    def session_username(self):
        return f"{PUBLIC_USER_ID}{self.id.hex}@{self.public_webform.domain}.commcarehq.org"


class PublicFormUser:
    """
    Duck-typed CouchUser proxy used during a public form session request. Wraps
    a PublicFormSession and exposes the minimal CouchUser interface that
    public-form request paths read.
    """

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        """The underlying PublicFormSession (e.g. for session consumption)."""
        return self._session

    @property
    def user_id(self):
        # Shared attribution id for every public submission.
        return PUBLIC_USER_ID

    @property
    def get_id(self):
        return self.user_id

    @property
    def username(self):
        return self._session.session_username

    @property
    def raw_username(self):
        return self.username

    @property
    def is_authenticated(self):
        return True

    @property
    def language(self):
        # Set None to fall back to Django's cookie-based language resolution
        return None

    def is_web_user(self):
        return False

    def is_commcare_user(self):
        return False

    def has_permission(self, domain, permission, data=None):
        return (
            permission == 'access_mobile_endpoints'
            and domain == self._session.public_webform.domain
        )

    def get_domains(self):
        return [self._session.public_webform.domain]

    def to_ota_restore_user(self, domain, request_user=None):
        return OTARestorePublicFormUser(domain, self, request_user=request_user)


class OTARestorePublicFormUser(OTARestoreUser):
    """
    OTA restore user for a public form session. Sandboxed: no owner ids, no
    locations, no role, no case sharing, so the restore payload contains only
    the user registration block and global fixtures, never project case data.
    """

    def __init__(self, domain, couch_user, **kwargs):
        assert isinstance(couch_user, PublicFormUser)
        super().__init__(domain, couch_user, **kwargs)

    @property
    def password(self):
        return ''

    @property
    def date_joined(self):
        return self._couch_user.session.created_at

    @property
    def user_session_data(self):
        return {}

    @property
    def sql_location(self):
        return None

    def get_owner_ids(self):
        return []

    def get_location_ids(self, domain):
        return []

    def get_sql_locations(self, domain):
        return SQLLocation.objects.none()

    def get_role(self, domain):
        return None

    def get_case_sharing_groups(self):
        return []

    def get_fixture_data_items(self):
        return []

    def get_commtrack_location_id(self):
        return None

    def get_call_center_indicators(self, config):
        return None
