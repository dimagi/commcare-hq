from __future__ import absolute_import
from __future__ import unicode_literals
import copy
import hashlib
import json
import logging
import os
import platform
import uuid
from datetime import datetime

from django.utils.functional import cached_property

from dimagi.ext.couchdbkit import (
    Document, StringProperty, DateTimeProperty, StringListProperty, DictProperty, IntegerProperty
)
from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.contrib.contenttypes.models import ContentType

from auditcare import utils
import six
from io import open

log = logging.getLogger(__name__)


try:
    from django.contrib.auth.signals import user_logged_in, user_logged_out
except:
    if getattr(settings, 'AUDITCARE_LOG_ERRORS', True):
        log.error("Error, django.contrib.auth signals not available in this version of django yet.")
    user_logged_in = None
    user_logged_out = None

from auditcare.signals import user_login_failed


def make_uuid():
    return uuid.uuid4().hex


def getdate():
    return datetime.utcnow()

#class AuditManager(models.Manager):
#    pass


STANDARD_HEADER_KEYS = ['X_FORWARDED_FOR', 'X_FORWARDED_HOST', 'X_FORWARDED_SERVER', 'VIA', 'HTTP_REFERER', 'REQUEST_METHOD',
  'QUERY_STRING', 'HTTP_ACCEPT_CHARSET',
 'HTTP_CONNECTION', 'HTTP_COOKIE', 'SERVER_NAME', 'SERVER_PORT',
   'HTTP_ACCEPT', 'REMOTE_ADDR', 'HTTP_ACCEPT_LANGUAGE', 'CONTENT_TYPE', 'HTTP_ACCEPT_ENCODING']


@six.python_2_unicode_compatible
class AuditEvent(Document):
    user = StringProperty() #the user committing the action
    base_type = StringProperty(default="AuditEvent") #for subclassing this needs to stay consistent
    #subclasses will be know directly from the doc_type, so it's not here.
    #doc_type = StringProperty() #Descriptor classifying this particular instance - this will be the child class's class name, with some modifications if need be
    event_date = DateTimeProperty(default=getdate)
    description = StringProperty() #particular instance details of this audit event

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
        elif user == None:
            audit.user = None
            audit.description = '[NullUser] '
        elif isinstance(user, User):
            audit.user = user.username
            audit.description = user.first_name + " " + user.last_name
        else:
            audit.user = user.username
            audit.description = ''
        return audit


class ModelActionAudit(AuditEvent):
    """
    Audit event to track the modification or editing of an auditable model

    For django models:
        the object_type will be the contenttype
        the object_uuid will be the model instance's PK
        the revision_id will be whatever is decided by the app

    for couch models:
        the object_type will be the doc_type
        the object_uuid will be theh doc's doc_id
        the revision_id will be the _rev as emitted by the 

    """
    object_type = StringProperty()
    object_uuid = StringProperty()
    revision_checksum = StringProperty()
    revision_id = StringProperty()
    archived_data = DictProperty() # the instance data of the model at this rev.  So at any given moment, the CURRENT instance of this model will be equal to this.

    #PRIOR values are stored here so as to show the delta of data.
    removed = DictProperty() #data/properties removed in this revision.
    added = DictProperty() # data/properties added in this revision
    changed = DictProperty() # data/properties changed in this revision

    next_id = StringProperty() #the doc_id of the next revision
    prev_id = StringProperty() #the doc_id of the previous revision

    def next(self):
        if self.next_id is not None:
            return self.__class__.get(self.next_id)
        else:
            return None

    def prev(self):
        if self.prev_id is not None:
            return self.__class__.get(self.prev_id)
        else:
            return None

    @property
    def summary(self):
        return "%s ID: %s" % (self.object_type, self.object_uuid)

    class Meta(object):
        app_label = 'auditcare'

    @classmethod
    def calculate_checksum(cls, instance_json, is_django=False):
        if is_django:
            json_string = json.dumps(instance_json)
        else:
            instance_copy = copy.deepcopy(instance_json)
            #if instance_copy.has_key('_rev'):
            #if it's an existing version, then save it
            instance_copy.pop('_rev')
            json_string = json.dumps(instance_copy)
        return hashlib.sha1(json_string.encode('utf-8') if six.PY3 else json_string).hexdigest()

    def compute_changes(self, save=False):
        """
        Instance method to compute the deltas for a given audit instance.
        Assumes two things:
        1:  self.archived_data must be set
        2:  self.prev_id must be set too.

        returns None
        """
        if self.prev_id is None:
            log.error("Error, trying to compute changes where a previous pointer isn't set")
            return None
        if self.archived_data is None:
            log.error("Error, trying to compute changes when the archived_data for CURRENT has not been set")
            return None
        prev_rev = self.prev()

        if prev_rev.revision_checksum == self.revision_checksum:
            #sanity check, do nothing at no changes
            return None
        removed, added, changed = utils.dict_diff(self.archived_data, prev_rev.to_json()['archived_data'])
        self.removed = removed
        self.added = added
        self.changed = changed
        if save:
            self.save()


    def resolved_changed_fields(self, filters=None, excludes=None):
        """
        Generator for changed field values yielding
        (field_key, (from_val, to_val))
        This answers the question
        'Field X was changed from_val to to_val'
        """
        changed, added, removed = self.get_changed_fields(filters=filters, excludes=excludes)
        #returns generated tuples of (field, (from_val, to_val))
        for ckey in changed:
            #get self's archived value, which is the "old" value
            prior_val = self.changed[ckey]
            next_val = self.archived_data[ckey]
            if next_val != prior_val:
                yield (ckey, (prior_val, next_val))


    def get_changed_fields(self, filters=None, excludes=None):
        """
        Gets all the changed fields for an audit event.

        Returns a tuple of field KEYS that lets you access the changed fields and also get the values from them programmatically later.
        """
        changed_keys = list(self.changed)
        added_keys = list(self.added)
        removed_keys = list(self.removed)

        if filters:
            are_changed = [x for x in filters if x in changed_keys]
            are_added = [x for x in filters if x in added_keys]
            are_removed = [x for x in filters if x in removed_keys]
        else:
            are_changed = changed_keys[:]
            are_added = added_keys[:]
            are_removed = removed_keys[:]

        if excludes:
            final_changed = [x for x in are_changed if x not in excludes]
            final_added = [x for x in are_added if x not in excludes]
            final_removed = [x for x in are_removed if x not in excludes]
        else:
            final_changed = are_changed
            final_added = are_added
            final_removed = are_removed

        return final_changed, final_added, final_removed

    @classmethod
    def _save_model_audit(cls, audit, instance_id, instance_json, revision_id, model_class_name, is_django=False):
        """

        """

        db = AuditEvent.get_db()
        prior_revs = db.view('auditcare/model_actions_by_id', key=[model_class_name, instance_id], reduce=False).all()

        audit.description += "Save %s" % (model_class_name)
        audit.object_type = model_class_name
        audit.object_uuid = instance_id
        audit.archived_data = instance_json
        audit.revision_checksum = cls.calculate_checksum(instance_json, is_django=is_django)

        if len(prior_revs) == 0:
            if is_django:
                audit.revision_id = "1"
            else:
                audit.revision_id = revision_id
            audit.save()
        else:
            #this has been archived before.  Get the last one and compare the checksum.
            sorted_revs = sorted(prior_revs, key=lambda x: x['value']['event_date'])
            #last_rev = sorted_revs[-1]['value']['rev']
            last_checksum = sorted_revs[-1]['value']['checksum']
            if is_django:
                #for django models, increment an integral counter.
                try:
                    audit.revision_id = str(len(prior_revs) + 1) #str(int(last_rev) + 1)
                except:
                    log.error("Error, last revision for object %s is not an integer, resetting to one")
                    audit.revision_id = "1"
            else:
                #for django set the revision id to the current document's revision id.
                audit.revision_id = revision_id

            if last_checksum == audit.revision_checksum:
                #no actual changes made on this save, do nothing
                log.debug("No data change, not creating audit event")
            else:
                audit.next_id = None #this is the head
                audit.prev_id = sorted_revs[-1]['id']
                audit.compute_changes(save=False)
                audit.save()

    @classmethod
    def audit_django_save(cls, model_class, instance, instance_json, user):
        audit = cls.create_audit(cls, user)
        instance_id = six.text_type(instance.id)
        revision_id = None
        cls._save_model_audit(audit, instance_id, instance_json, revision_id, model_class.__name__, is_django=True)


    @classmethod
    def audit_couch_save(cls, model_class, instance, instance_json, user):
        audit = cls.create_audit(cls, user)
        instance_id = instance._id
        revision_id = instance._rev
        cls._save_model_audit(audit, instance_id, instance_json, revision_id, model_class.__name__, is_django=False)

setattr(AuditEvent, 'audit_django_save', ModelActionAudit.audit_django_save)
setattr(AuditEvent, 'audit_couch_save', ModelActionAudit.audit_couch_save)


class NavigationEventAudit(AuditEvent):
    """
    Audit event to track happenings within the system, ie, view access
    """
    request_path = StringProperty()
    ip_address = StringProperty()
    user_agent = StringProperty()

    view = StringProperty() #the fully qualifid view name
    view_kwargs = DictProperty()
    headers = DictProperty() #the request.META?
    session_key = StringProperty() #in the future possibly save some disk space by storing user agent and IP stuff in a separte session document?

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
                audit.request_path = "%s?%s" % (
                    request.path, '&'.join(["%s=%s" % (x, request.GET[x]) for x in request.GET.keys()]))
            else:
                audit.request_path = request.path
            audit.ip_address = utils.get_ip(request)
            audit.user_agent = request.META.get('HTTP_USER_AGENT', '<unknown>')
            audit.view = "%s.%s" % (view_func.__module__, view_func.__name__)
            for k in STANDARD_HEADER_KEYS:
                header_item = request.META.get(k, None)
                if header_item is not None:
                    audit.headers[k] = header_item
            #audit.headers = request.META #it's a bit verbose to go to that extreme, TODO: need to have targeted fields in the META, but due to server differences, it's hard to make it universal.
            audit.session_key = request.session.session_key
            audit.extra = extra
            audit.view_kwargs = view_kwargs
            audit.save()
            return audit
        except Exception as ex:
            log.error("NavigationEventAudit.audit_view error: %s", ex)

setattr(AuditEvent, 'audit_view', NavigationEventAudit.audit_view)

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
    session_key = StringProperty() #the django auth session key

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
        audit.ip_address = utils.get_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '<unknown>')
        audit.http_accept = request.META.get('HTTP_ACCEPT', '<unknown>')
        audit.path_info = request.META.get('PATH_INFO', '<unknown>')
        audit.user_agent = ua
        audit.access_type = 'login'
        audit.description = "Login Success"
        audit.session_key = request.session.session_key
        audit.get_data = [] #[query2str(request.GET.items())]
        audit.post_data = []
        audit.save()

    @classmethod
    def audit_login_failed(cls, request, username, *args, **kwargs):
        '''Creates an instance of a Access log.
        '''
        audit = cls.create_audit(cls, username)
        audit.ip_address = utils.get_ip(request)
        audit.access_type = 'login_failed'
        if username != None:
            audit.description = "Login Failure: %s" % (username)
        else:
            audit.description = "Login Failure"
        audit.session_key = request.session.session_key
        audit.save()

    @classmethod
    def audit_logout(cls, request, user):
        '''Log a logout event'''
        audit = cls.create_audit(cls, user)
        audit.ip_address = utils.get_ip(request)

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


class AuditCommand(AuditEvent):
    """
    Audit wrapper class to capture environmental information around a management command run.
    """
    sudo_user = StringProperty()

    # ip address if available of logged in user running cmd
    ip_address = StringProperty()
    pid = IntegerProperty()


    @classmethod
    def audit_command(cls):
        """
        Log a management command with available information

        The command line run will be recorded in the self.description
        """
        audit = cls.create_audit(cls, None)
        puname = platform.uname()
        audit.user = os.environ.get('USER', None)
        audit.pid = os.getpid()

        if 'SUDO_COMMAND' in os.environ:
            audit.description = os.environ.get('SUDO_COMMAND', None)
            audit.sudo_user = os.environ.get('SUDO_USER', None)
        else:

            # Note: this is a work in progress
            # getting command line arg from a pid is a system specific trick
            # only supporting linux at this point, adding other OS's can be done later
            # This is largely for production logging of these commands.
            if puname[0] == 'Linux':
                with open('/proc/%s/cmdline' % audit.pid, 'r', encoding='utf-8') as fin:
                    cmd_args = fin.read()
                    audit.description = cmd_args.replace('\0', ' ')
            elif puname[0] == 'Darwin':
                # mac osx
                # TODO
                pass
            elif puname[0] == 'Windows':
                # TODO
                pass

        audit.save()


setattr(AuditEvent, 'audit_command', AuditCommand.audit_command)


def audit_login(sender, **kwargs):
    AuditEvent.audit_login(kwargs["request"], kwargs["user"], True) # success

if user_logged_in:
    user_logged_in.connect(audit_login)


def audit_logout(sender, **kwargs):
    AuditEvent.audit_logout(kwargs["request"], kwargs["user"])

if user_logged_out:
    user_logged_out.connect(audit_logout)


def audit_login_failed(sender, **kwargs):
    AuditEvent.audit_login_failed(kwargs["request"], kwargs["username"])

user_login_failed.connect(audit_login_failed)
