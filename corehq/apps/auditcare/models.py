import logging
import uuid
from datetime import datetime

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property

from dimagi.ext.couchdbkit import (
    DateTimeProperty,
    DictProperty,
    Document,
    IntegerProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.web import get_ip

from .signals import user_login_failed

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


class AuditEvent(Document):
    user = StringProperty()  # the user committing the action
    base_type = StringProperty(default="AuditEvent")  # for subclassing this needs to stay consistent
    # subclasses will be known directly from the doc_type, so it's not here.
    event_date = DateTimeProperty(default=getdate)
    description = StringProperty()  # particular instance details of this audit event

    @property
    def summary(self):
        try:
            ct = ContentType.objects.get(model=self.doc_type.lower())
            return ct.model_class().objects.get(id=self.id).summary
        except Exception:
            return ""

    class Meta(object):
        app_label = 'auditcare'

    def __str__(self):
        return "[%s] %s" % (self.doc_type, self.description)

    @classmethod
    def create_audit(cls, model_class, user):
        """
        Returns a premade audit object in memory to be completed by the subclasses.
        """
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
            audit.user = user.username
            audit.description = ''
        return audit


class NavigationEventAudit(AuditEvent):
    """
    Audit event to track happenings within the system, ie, view access
    """
    request_path = StringProperty()
    ip_address = StringProperty()
    user_agent = StringProperty()

    view = StringProperty()  # the fully qualifid view name
    view_kwargs = DictProperty()
    headers = DictProperty()  # the request.META?
    # in the future possibly save some disk space by storing user agent and IP stuff in a separte session document?
    session_key = StringProperty()

    status_code = IntegerProperty()

    extra = DictProperty()

    @property
    def summary(self):
        return "%s from %s" % (self.request_path, self.ip_address)

    class Meta(object):
        app_label = 'auditcare'

    @cached_property
    def domain(self):
        from corehq.apps.domain.utils import get_domain_from_url
        return get_domain_from_url(self.request_path)

    @classmethod
    def audit_view(cls, request, user, view_func, view_kwargs, extra={}):
        """Creates an instance of a Access log."""
        try:
            audit = cls.create_audit(cls, user)
            audit.description += "View"
            if len(list(request.GET)) > 0:
                params = "&".join(f"{x}={request.GET[x]}" for x in request.GET.keys())
                audit.request_path = f"{request.path}?{params}"
            else:
                audit.request_path = request.path
            audit.ip_address = get_ip(request)
            audit.user_agent = request.META.get('HTTP_USER_AGENT', '<unknown>')
            audit.view = "%s.%s" % (view_func.__module__, view_func.__name__)
            for k in STANDARD_HEADER_KEYS:
                header_item = request.META.get(k, None)
                if header_item is not None:
                    audit.headers[k] = header_item
            # it's a bit verbose to go to that extreme, TODO: need to have
            # targeted fields in the META, but due to server differences, it's
            # hard to make it universal.
            #audit.headers = request.META
            audit.session_key = request.session.session_key
            audit.extra = extra
            audit.view_kwargs = view_kwargs
            audit.save()
            return audit
        except Exception as ex:
            log.error("NavigationEventAudit.audit_view error: %s", ex)


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


class AccessAudit(AuditEvent):
    access_type = StringProperty(choices=ACCESS_CHOICES)
    ip_address = StringProperty()
    session_key = StringProperty()  # the django auth session key

    user_agent = StringProperty()

    get_data = StringListProperty()
    post_data = StringListProperty()
    http_accept = StringProperty()
    path_info = StringProperty()

    failures_since_start = IntegerProperty()

    class Meta(object):
        app_label = 'auditcare'

    @property
    def summary(self):
        return "%s from %s" % (self.access_type, self.ip_address)

    @classmethod
    def audit_login(cls, request, user, *args, **kwargs):
        '''Creates an instance of a Access log.
        '''
        audit = cls.create_audit(cls, user)
        audit.ip_address = get_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '<unknown>')
        audit.http_accept = request.META.get('HTTP_ACCEPT', '<unknown>')
        audit.path_info = request.META.get('PATH_INFO', '<unknown>')
        audit.user_agent = ua
        audit.access_type = 'login'
        audit.description = "Login Success"
        audit.session_key = request.session.session_key
        audit.get_data = []  # [query2str(request.GET.items())]
        audit.post_data = []
        audit.save()

    @classmethod
    def audit_login_failed(cls, request, username, *args, **kwargs):
        '''Creates an instance of a Access log.
        '''
        audit = cls.create_audit(cls, username)
        audit.ip_address = get_ip(request)
        audit.access_type = 'login_failed'
        if username is not None:
            audit.description = "Login Failure: %s" % (username)
        else:
            audit.description = "Login Failure"
        audit.session_key = request.session.session_key
        audit.save()

    @classmethod
    def audit_logout(cls, request, user):
        '''Log a logout event'''
        audit = cls.create_audit(cls, user)
        audit.ip_address = get_ip(request)

        if user == AnonymousUser:
            audit.description = "Logout anonymous"
        elif user is None:
            audit.description = "None"
        else:
            audit.description = "Logout %s" % (user.username)
        audit.access_type = 'logout'
        audit.session_key = request.session.session_key
        audit.save()


setattr(AuditEvent, 'audit_login', AccessAudit.audit_login)
setattr(AuditEvent, 'audit_login_failed', AccessAudit.audit_login_failed)
setattr(AuditEvent, 'audit_logout', AccessAudit.audit_logout)


def audit_login(sender, **kwargs):
    AuditEvent.audit_login(kwargs["request"], kwargs["user"], True)  # success


if user_logged_in:
    user_logged_in.connect(audit_login)


def audit_logout(sender, **kwargs):
    AuditEvent.audit_logout(kwargs["request"], kwargs["user"])


if user_logged_out:
    user_logged_out.connect(audit_logout)


def audit_login_failed(sender, **kwargs):
    AuditEvent.audit_login_failed(kwargs["request"], kwargs["username"])


user_login_failed.connect(audit_login_failed)


def wrap_audit_event(event):
    doc_type = event['doc_type']
    cls = {
        'NavigationEventAudit': NavigationEventAudit,
        'AccessAudit': AccessAudit,
    }.get(doc_type, None)
    if not cls:
        raise ValueError(f"Unknow doc type for audit event: {doc_type}")

    return cls.wrap(event)
