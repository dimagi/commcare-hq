import logging
import uuid
from datetime import datetime

import architect

from django.contrib.auth.models import AnonymousUser, User
from django.db import models

from dimagi.utils.web import get_ip

from corehq.apps.domain.utils import get_domain_from_url
from corehq.util.models import (
    ForeignValue,
    NullJsonField,
    TruncatingCharField,
    foreign_init,
)

log = logging.getLogger(__name__)


def make_uuid():
    return uuid.uuid4().hex


def getdate():
    return datetime.utcnow()


STANDARD_HEADER_KEYS = [
    'X_FORWARDED_FOR',
    'X_FORWARDED_HOST',
    'X_FORWARDED_SERVER',
    'VIA',
    'HTTP_REFERER',
    'REQUEST_METHOD',
    'QUERY_STRING',
    'HTTP_ACCEPT_CHARSET',
    'HTTP_CONNECTION',
    'HTTP_COOKIE',
    'SERVER_NAME',
    'SERVER_PORT',
    'HTTP_ACCEPT',
    'REMOTE_ADDR',
    'HTTP_ACCEPT_LANGUAGE',
    'CONTENT_TYPE',
    'CONTENT_LENGTH',
    'HTTP_ACCEPT_ENCODING',
    'HTTP_USER_AGENT',
    # settings.AUDIT_TRACE_ID_HEADER (django-ified) will be added here
]


def get_standard_headers(request_meta, exclude=None):
    exclude = exclude or []
    headers = {}
    for k in STANDARD_HEADER_KEYS:
        if k not in exclude:
            header_item = request_meta.get(k, None)
            if header_item is not None:
                headers[k] = header_item
    return headers


class UserAgent(models.Model):
    value = models.CharField(max_length=255, db_index=True, unique=True)


class HttpAccept(models.Model):
    value = models.CharField(max_length=255, db_index=True, unique=True)


class ViewName(models.Model):
    value = models.CharField(max_length=255, db_index=True, unique=True)


class AuditEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.CharField(max_length=255, null=True, blank=True)
    domain = models.CharField(max_length=126, null=True, blank=True)
    event_date = models.DateTimeField(default=getdate, db_index=True)
    path = TruncatingCharField(max_length=255, blank=True, default='')
    ip_address = models.CharField(max_length=45, blank=True, default='')
    session_key = models.CharField(max_length=255, blank=True, null=True)
    user_agent_fk = models.ForeignKey(
        UserAgent, null=True, db_index=False, on_delete=models.PROTECT)
    user_agent = ForeignValue(user_agent_fk, truncate=True)
    couch_id = models.CharField(max_length=126, null=True)

    @property
    def doc_type(self):
        return type(self).__name__

    @property
    def description(self):
        raise NotImplementedError("abstract property")

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["user", "event_date"]),
            models.Index(fields=["domain", "event_date"]),
        ]

    def __str__(self):
        return "[%s] %s" % (self.doc_type, self.description)

    @classmethod
    def create_audit(cls, request, user):
        audit = cls()
        audit.domain = get_domain(request)
        audit.path = request.path
        audit.ip_address = get_ip(request)
        audit.session_key = request.session.session_key
        audit.user_agent = request.META.get('HTTP_USER_AGENT')
        if isinstance(user, AnonymousUser):
            audit.user = None
        elif user is None:
            audit.user = None
        elif isinstance(user, User):
            audit.user = user.username
        else:
            audit.user = user
        return audit


@architect.install('partition', type='range', subtype='date', constraint='month', column='event_date')
@foreign_init
class NavigationEventAudit(AuditEvent):
    """
    Audit event to track happenings within the system, ie, view access
    """
    params = TruncatingCharField(max_length=4096, blank=True, default='')
    view_fk = models.ForeignKey(
        ViewName, null=True, db_index=False, on_delete=models.PROTECT)
    view = ForeignValue(view_fk, truncate=True)
    view_kwargs = NullJsonField(default=dict)
    headers = NullJsonField(default=dict)
    status_code = models.SmallIntegerField(default=0)

    class Meta(AuditEvent.Meta):
        constraints = [
            models.UniqueConstraint(fields=['couch_id'], condition=models.Q(couch_id__isnull=False),
                                    name="audit_nav_couch_875bc_idx"),
        ]

    @property
    def description(self):
        return self.user or ""

    @property
    def request_path(self):
        return f"{self.path}?{self.params}"

    @property
    def request_method(self):
        headers = self.headers or {}
        return headers.get("REQUEST_METHOD", "")

    @classmethod
    def audit_view(cls, request, user, view_func, view_kwargs):
        audit = cls.create_audit(request, user)
        if request.GET:
            audit.params = request.META.get("QUERY_STRING", "")
        audit.view = "%s.%s" % (view_func.__module__, view_func.__name__)
        audit.headers.update(get_standard_headers(request.META, exclude=['HTTP_USER_AGENT']))
        # it's a bit verbose to go to that extreme, TODO: need to have
        # targeted fields in the META, but due to server differences, it's
        # hard to make it universal.
        audit.view_kwargs = view_kwargs
        return audit


ACCESS_LOGIN = 'i'
ACCESS_LOGOUT = 'o'
ACCESS_FAILED = 'f'
ACCESS_CHOICES = {
    ACCESS_LOGIN: "Login",
    ACCESS_LOGOUT: "Logout",
    ACCESS_FAILED: "Login failed",
}


@architect.install('partition', type='range', subtype='date', constraint='month', column='event_date')
@foreign_init
class AccessAudit(AuditEvent):
    access_type = models.CharField(max_length=1, choices=ACCESS_CHOICES.items())
    http_accept_fk = models.ForeignKey(
        HttpAccept, null=True, db_index=False, on_delete=models.PROTECT)
    http_accept = ForeignValue(http_accept_fk, truncate=True)
    trace_id = models.CharField(max_length=127, null=True, blank=True)

    class Meta(AuditEvent.Meta):
        constraints = [
            models.UniqueConstraint(fields=['couch_id'], condition=models.Q(couch_id__isnull=False),
                                    name="audit_access_couch_10d1b_idx"),
        ]

    # Optional (django-ified) settings.AUDIT_TRACE_ID_HEADER set by AuditcareConfig
    trace_id_header = None

    @property
    def description(self):
        return f"{ACCESS_CHOICES[self.access_type]}: {self.user or ''}"

    @classmethod
    def create_audit(cls, request, user, access_type):
        '''Creates an instance of a Access log.'''
        audit = super().create_audit(request, user)
        audit.http_accept = request.META.get('HTTP_ACCEPT')
        audit.access_type = access_type
        if cls.trace_id_header is not None:
            audit.trace_id = request.META.get(cls.trace_id_header)
        return audit

    @classmethod
    def audit_login(cls, request, user, *args, **kwargs):
        audit = cls.create_audit(request, user, ACCESS_LOGIN)
        audit.save()

    @classmethod
    def audit_login_failed(cls, request, username, *args, **kwargs):
        audit = cls.create_audit(request, username, ACCESS_FAILED)
        audit.save()

    @classmethod
    def audit_logout(cls, request, user):
        audit = cls.create_audit(request, user, ACCESS_LOGOUT)
        audit.save()


def audit_login(sender, *, request, user, **kwargs):
    AccessAudit.audit_login(request, user)  # success


def audit_logout(sender, *, request, user, **kwargs):
    AccessAudit.audit_logout(request, user)


def audit_login_failed(sender, *, request, credentials, **kwargs):
    AccessAudit.audit_login_failed(request, credentials["username"])


def get_domain(request):
    domain = get_domain_from_url(request.path)
    domain2 = getattr(request, "domain", None)
    if domain2:
        if not domain:
            domain = domain2
        elif domain != domain2:
            log.error("domain mismatch for request %s: %r != %r",
                request.path, domain, domain2)
    return domain
