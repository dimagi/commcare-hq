import logging
import uuid
from datetime import datetime

import architect

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    #user_login_failed,
)
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.functional import cached_property

from dimagi.utils.web import get_ip

from corehq.apps.domain.utils import get_domain_from_url
from corehq.util.models import ForeignValue, NullJsonField, foreign_value_init

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
    'HTTP_ACCEPT_ENCODING',
]


class UserAgent(models.Model):
    value = models.CharField(max_length=255, db_index=True)


class HttpAccept(models.Model):
    value = models.CharField(max_length=255, db_index=True)


class ViewName(models.Model):
    value = models.CharField(max_length=255, db_index=True)


class AuditEvent(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.CharField(max_length=255, null=True, blank=True)
    event_date = models.DateTimeField(default=getdate, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    path = models.CharField(max_length=255, blank=True, default='')

    @property
    def doc_type(self):
        return type(self).__name__

    @property
    def summary(self):
        try:
            ct = ContentType.objects.get(model=self.doc_type.lower())
            return ct.model_class().objects.get(id=self.id).summary
        except Exception:
            return ""

    class Meta:
        abstract = True
        index_together = [("user", "event_date")]

    def __str__(self):
        return "[%s] %s" % (self.doc_type, self.description)

    @classmethod
    def create_audit(cls, user):
        audit = cls()
        if isinstance(user, AnonymousUser):
            audit.user = None
            audit.description = "[AnonymousAccess] "
        elif user is None:
            audit.user = None
            audit.description = '[NullUser] '
        elif isinstance(user, User):
            audit.user = user.username
            audit.description = user.first_name + " " + user.last_name
        else:
            audit.user = user
            audit.description = ''
        return audit


@architect.install('partition', type='range', subtype='date', constraint='month', column='event_date')
@foreign_value_init
class NavigationEventAudit(AuditEvent):
    """
    Audit event to track happenings within the system, ie, view access
    """
    params = models.CharField(max_length=512, blank=True, default='')
    ip_address = models.CharField(max_length=45, blank=True, default='')
    user_agent_fk = models.ForeignKey(
        UserAgent, null=True, db_index=False, on_delete=models.PROTECT)
    user_agent = ForeignValue(user_agent_fk, truncate=True)
    view_fk = models.ForeignKey(
        ViewName, null=True, db_index=False, on_delete=models.PROTECT)
    view = ForeignValue(view_fk, truncate=True)
    view_kwargs = NullJsonField(default=dict)
    headers = NullJsonField(default=dict)
    session_key = models.CharField(max_length=255, blank=True, null=True)
    status_code = models.SmallIntegerField(default=0)
    extra = NullJsonField(default=dict)

    @property
    def summary(self):
        return "%s from %s" % (self.request_path, self.ip_address)

    @cached_property
    def domain(self):
        return get_domain_from_url(self.path)

    @cached_property
    def request_path(self):
        return f"{self.path}?{self.params}"

    @classmethod
    def audit_view(cls, request, user, view_func, view_kwargs, extra={}):
        try:
            audit = cls.create_audit(user)
            if request.GET:
                audit.path = request.path
                audit.params = "&".join(f"{x}={request.GET[x]}" for x in request.GET)
            else:
                audit.path = request.path
            audit.ip_address = get_ip(request)
            audit.user_agent = request.META.get('HTTP_USER_AGENT')
            audit.view = "%s.%s" % (view_func.__module__, view_func.__name__)
            for k in STANDARD_HEADER_KEYS:
                header_item = request.META.get(k, None)
                if header_item is not None:
                    audit.headers[k] = header_item
            # it's a bit verbose to go to that extreme, TODO: need to have
            # targeted fields in the META, but due to server differences, it's
            # hard to make it universal.
            audit.session_key = request.session.session_key
            audit.extra = extra
            audit.view_kwargs = view_kwargs
            return audit
        except Exception:
            log.exception("NavigationEventAudit.audit_view error")


ACCESS_LOGIN = 'login'
ACCESS_LOGOUT = 'logout'
ACCESS_FAILED = 'login_failed'
ACCESS_USER_LOCKOUT = 'user_lockout'
ACCESS_IP_LOCKOUT = 'ip_lockout'
ACCESS_PASSWORD = 'password_change'
ACCESS_CHOICES = (
    (ACCESS_LOGIN, "Login"),
    (ACCESS_LOGOUT, "Logout"),
    (ACCESS_FAILED, "Failed Login"),
    (ACCESS_USER_LOCKOUT, "User Lockout"),
    (ACCESS_IP_LOCKOUT, "IP Lockout"),
    (ACCESS_PASSWORD, "Password Change"),
)


@architect.install('partition', type='range', subtype='date', constraint='month', column='event_date')
@foreign_value_init
class AccessAudit(AuditEvent):
    access_type = models.CharField(max_length=16, choices=ACCESS_CHOICES)
    ip_address = models.CharField(max_length=45, blank=True, default='')
    session_key = models.CharField(max_length=255, blank=True, null=True)
    user_agent_fk = models.ForeignKey(
        UserAgent, null=True, db_index=False, on_delete=models.PROTECT)
    user_agent = ForeignValue(user_agent_fk, truncate=True)
    http_accept_fk = models.ForeignKey(
        HttpAccept, null=True, db_index=False, on_delete=models.PROTECT)
    http_accept = ForeignValue(http_accept_fk, truncate=True)
    failures_since_start = models.SmallIntegerField(null=True)

    @property
    def summary(self):
        return "%s from %s" % (self.access_type, self.ip_address)

    @classmethod
    def create_audit(cls, request, user, access_type):
        '''Creates an instance of a Access log.'''
        audit = super().create_audit(user)
        audit.ip_address = get_ip(request) or ''
        audit.http_accept = request.META.get('HTTP_ACCEPT')
        audit.path = request.META.get('PATH_INFO', '')
        audit.user_agent = request.META.get('HTTP_USER_AGENT')
        audit.access_type = access_type
        audit.session_key = request.session.session_key
        return audit

    @classmethod
    def audit_login(cls, request, user, *args, **kwargs):
        audit = cls.create_audit(request, user, ACCESS_LOGIN)
        audit.save()

    @classmethod
    def audit_login_failed(cls, request, username, *args, **kwargs):
        audit = cls.create_audit(request, username, ACCESS_FAILED)
        if username is not None:
            audit.description = "Login Failure: %s" % (username)
        else:
            audit.description = "Login Failure"
        audit.save()

    @classmethod
    def audit_logout(cls, request, user):
        '''Log a logout event'''
        audit = cls.create_audit(request, user, ACCESS_LOGOUT)

        if user == AnonymousUser:
            audit.description = "Logout anonymous"
        elif user is None:
            audit.description = "None"
        else:
            audit.description = "Logout %s" % (user.username)
        audit.save()


def audit_login(sender, *, request, user, **kwargs):
    AccessAudit.audit_login(request, user)  # success


def audit_logout(sender, *, request, user, **kwargs):
    AccessAudit.audit_logout(request, user)


def audit_login_failed(sender, *, request, credentials, **kwargs):
    AccessAudit.audit_login_failed(request, credentials["username"])


user_logged_in.connect(audit_login)
user_logged_out.connect(audit_logout)
#user_login_failed.connect(audit_login_failed)  FIXME


def wrap_audit_event(event):
    doc_type = event['doc_type']
    cls = {
        'NavigationEventAudit': NavigationEventAudit,
        'AccessAudit': AccessAudit,
    }.get(doc_type, None)
    if not cls:
        raise ValueError(f"Unknow doc type for audit event: {doc_type}")

    return cls.wrap(event)
