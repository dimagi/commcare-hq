
"""
couch models go here
"""
from __future__ import absolute_import

from datetime import datetime
from django.contrib.auth.models import User
from django.db import models
from django.http import Http404, HttpResponseForbidden
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.couch.database import get_db
from djangocouchuser.models import CouchUserProfile
from couchdbkit.ext.django.schema import *
from djangocouch.utils import model_to_doc
from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.users.util import django_user_from_couch_id, \
    couch_user_from_django_user
from dimagi.utils.mixins import UnicodeMixIn
import logging
from corehq.apps.reports.models import ReportNotification
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.core.urlresolvers import reverse
from dimagi.utils.django.email import send_HTML_email
from casexml.apps.phone.models import User as CaseXMLUser
from corehq.apps.users.exceptions import NoAccountException
from dimagi.utils.dates import force_to_datetime

COUCH_USER_AUTOCREATED_STATUS = 'autocreated'

def _add_to_list(list, obj, default):
    if obj in list:
        list.remove(obj)
    if default:
        ret = [obj]
        ret.extend(list)
        return ret
    else:
        list.append(obj)
    return list
    
    
def _get_default(list):
    return list[0] if list else None

class Permissions(object):
    EDIT_USERS = 'edit-users'
    EDIT_DATA = 'edit-data'
    EDIT_APPS = 'edit-apps'
    LOG_IN = 'log-in'
    AVAILABLE_PERMISSIONS = [EDIT_DATA, EDIT_USERS, EDIT_APPS, LOG_IN]
    
class DomainMembership(DocumentSchema):
    """
    Each user can have multiple accounts on the 
    web domain. This is primarily for Dimagi staff.
    """

    domain = StringProperty()
    is_admin = BooleanProperty(default=False)
    permissions = StringListProperty()
    last_login = DateTimeProperty()
    date_joined = DateTimeProperty()
    
    class Meta:
        app_label = 'users'

from .old_couch_user import CouchUser as OldCouchUser

class DjangoUserMixin(DocumentSchema):
    username = StringProperty()
    first_name = StringProperty()
    last_name = StringProperty()
    email = StringProperty()
    password = StringProperty()
    is_staff = BooleanProperty()
    is_active = BooleanProperty()
    is_superuser = BooleanProperty()
    last_login = DateTimeProperty()
    date_joined = DateTimeProperty()

class CouchUser(Document, DjangoUserMixin, UnicodeMixIn):

    """
    A user (for web and commcare)

    """

    domain = StringProperty() # for CommCareAccounts
    domains = StringListProperty() # for WebAccount

    django_user = DictProperty()

    registering_device_id = StringProperty()
    device_ids = ListProperty()
    phone_numbers = ListProperty()

    user_data = DictProperty()

    domain_membership = SchemaListProperty(DomainMembership)

    created_on = DateTimeProperty()

    """
    For now, 'status' is things like:
        ('auto_created',     'Automatically created from form submission.'),
        ('phone_registered', 'Registered from phone'),
        ('site_edited',     'Manually added or edited from the HQ website.'),
    """
    status = StringProperty()

    _user = None
    _user_checked = False

    class AccountTypeError(Exception):
        pass
    class Inconsistent(Exception):
        pass

    @property
    def raw_username(self):
        if self.doc_type == "CommCareUser":
            return self.username.split("@")[0]
        else:
            return self.username

    def html_username(self):
        username = self.username
        if '@' in username:
            html = "<span class='user_username'>%s</span><span class='user_domainname'>@%s</span>" % \
                   tuple(username.split('@'))
        else:
            html = "<span class='user_username'>%s</span>" % username
        return html
    
    @property
    def userID(self):
        return self._id

    user_id = userID
    
    class Meta:
        app_label = 'users'

    def __unicode__(self):
        return "couch user %s" % self.get_id

    def get_email(self):
        return self.email
    
    @property
    def full_name(self):
        return "%s %s" % (self.first_name, self.last_name)

    formatted_name = full_name
        
    def get_scheduled_reports(self):
        return ReportNotification.view("reports/user_notifications", key=self.get_id, include_docs=True).all()

    def save(self, **kwargs):
        # Call the "real" save() method.
        super(CouchUser, self).save(**kwargs)

    def delete(self):
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
        super(CouchUser, self).delete() # Call the "real" delete() method.

    def get_django_user(self):
        return User.objects.get(pk=self.django_user['id'])

    def add_phone_number(self, phone_number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(phone_number, basestring):
            phone_number = str(phone_number)
        self.phone_numbers = _add_to_list(self.phone_numbers, phone_number, default)
        
    @property
    def default_phone_number(self):
        return _get_default(self.phone_numbers)

    @property
    def couch_id(self):
        return self._id

    # Couch view wrappers
    @classmethod
    def phone_users_by_domain(cls, domain):
        return CouchUser.view("users/phone_users_by_domain",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
        )

class CommCareUser(CouchUser):
    @classmethod
    def commcare_users_by_domain(cls, domain):
        return CouchUser.view("users/commcare_users_by_domain",
            reduce=False,
            key=domain,
            include_docs=True,
        )

    def is_commcare_user(self):
        return True
    
    def add_commcare_account(self, domain, device_id, user_data=None):
        """
        Adds a commcare account to this.
        """
        if self.domain and self.domain != domain:
            raise self.Inconsistent("Tried to reinitialize commcare account to a different domain")
        self.domain = domain
        self.registering_device_id = device_id
        self.user_data = user_data or {}
        self.add_device_id(device_id=device_id)

    def add_device_id(self, device_id, default=False, **kwargs):
        """ Don't add phone devices if they already exist """
        self.device_ids = _add_to_list(self.device_ids, device_id, default)

    def to_casexml_user(self):
        return CaseXMLUser(user_id=self.userID,
                           username=self.raw_username,
                           password=self.password,
                           date_joined=self.date_joined,
                           user_data=self.user_data)

class WebUser(CouchUser):
    base_doc = 'CouchUser'

    @classmethod
    def from_django_user(cls, django_user):
        login_id = django_user.get_profile()._id
        assert(len(cls.view("users/couch_users_by_django_profile_id", include_docs=True, key=login_id)) == 0)
        couch_user = cls()
        couch_user._id = login_id
        couch_user.first_name = django_user.first_name
        couch_user.last_name = django_user.last_name
        couch_user.email = django_user.email
        return couch_user

    def is_commcare_user(self):
        return False

    def get_domain_membership(self, domain):
        for d in self.domain_memberships:
            if d.domain == domain:
                if domain not in self.domains:
                    raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
                return d
        if domain in self.domains:
            raise self.Inconsistent("Domain '%s' is in domain but not in domain_memberships" % domain)

    def add_domain_membership(self, domain, **kwargs):
        for d in self.domain_memberships:
            if d.domain == domain:
                if domain not in self.domains:
                    raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
                return
        self.domain_memberships.append(DomainMembership(domain=domain,
                                                        **kwargs))
        self.domains.append(domain)

    def is_domain_admin(self, domain=None):
        if not domain:
            # hack for template
            if hasattr(self, 'current_domain'):
                # this is a hack needed because we can't pass parameters from views
                domain = self.current_domain
            else:
                return False # no domain, no admin
        if self.is_superuser:
            return True
        dm = self.get_domain_membership(domain)
        if dm:
            return dm.is_admin
        else:
            return False

    @property
    def domain_names(self):
        domains = [dm.domain for dm in self.web_account.domain_memberships]
        if set(domains) == set(self.domains):
            return domains
        else:
            raise self.Inconsistent("domains and domain_memberships out of sync")

    def get_active_domains(self):
        domain_names = self.domain_names
        return Domain.objects.filter(name__in=domain_names)

    def is_member_of(self, domain_qs):
        if isinstance(domain_qs, basestring):
            return domain_qs in self.domain_names or self.is_superuser
        membership_count = domain_qs.filter(name__in=self.domain_names).count()
        if membership_count > 0:
            return True
        return False
    
    def set_permission(self, domain, permission, value, save=True):
        assert(permission in Permissions.AVAILABLE_PERMISSIONS)
        if self.has_permission(domain, permission) == value:
            return
        dm = self.get_domain_membership(domain)
        if value:
            dm.permissions.append(permission)
        else:
            dm.permissions = [p for p in dm.permissions if p != permission]
        if save:
            self.save()

    def reset_permissions(self, domain, permissions, save=True):
        dm = self.get_domain_membership(domain)
        dm.permissions = permissions
        if save:
            self.save()

    def has_permission(self, domain, permission):
        # is_admin is the same as having all the permissions set
        dm = self.get_domain_membership(domain)
        if self.is_domain_admin(domain):
            return True
        else:
            return permission in dm.permissions

    def get_role(self, domain=None):
        """
        Expose a simplified role-based understanding of permissions
        which maps to actual underlying permissions

        """
        if domain is None:
            # default to current_domain for django templates
            domain = self.current_domain

        if self.is_member_of(domain):
            if self.is_domain_admin(domain):
                role = 'admin'
            elif self.can_edit_apps(domain):
                role = "edit-apps"
            else:
                role = "read-only"
        else:
            role = None

        return role

    def set_role(self, domain, role):
        """
        A simplified role-based way to set permissions

        """
        dm = self.get_domain_membership(domain)
        dm.is_admin = False
        if role == "admin":
            dm.is_admin = True
        elif role == "edit-apps":
            self.reset_permissions(domain, [Permissions.EDIT_APPS])
        elif role == "read-only":
            self.reset_permissions(domain, [])
        else:
            raise KeyError()

    ROLE_LABELS = (
        ('admin', 'Admin'),
        ('edit-apps', 'App Editor'),
        ('read-only', 'Read Only')
    )
    def role_label(self, domain=None):
        if not domain:
            try:
                domain = self.current_domain
            except KeyError:
                return None
        return dict(self.ROLE_LABELS).get(self.get_role(domain), "Unknown Role")

    # these functions help in templates
    def can_edit_apps(self, domain):
        return self.has_permission(domain, Permissions.EDIT_APPS)
    def can_edit_users(self, domain):
        return self.has_permission(domain, Permissions.EDIT_USERS)

# this is a permissions decorator
def require_permission(permission):
    def decorator(view_func):
        def _inner(request, domain, *args, **kwargs):
            if hasattr(request, "couch_user") and (request.user.is_superuser or request.couch_user.has_permission(domain, permission)):
                return login_and_domain_required(view_func)(request, domain, *args, **kwargs)
            else:
                return HttpResponseForbidden()
        return _inner
    return decorator

"""
Django  models go here
"""
class Invitation(Document):
    """
    When we invite someone to a domain it gets stored here.
    """
    domain = StringProperty()
    email = StringProperty()
    is_domain_admin = BooleanProperty()
    invited_by = StringProperty()
    invited_on = DateTimeProperty()
    is_accepted = BooleanProperty(default=False)
    
    _inviter = None
    def get_inviter(self):
        if self._inviter == None:
            self._inviter = CouchUser.get(self.invited_by)
        return self._inviter
    
    def send_activation_email(self):

        url = "http://%s%s" % (Site.objects.get_current().domain, 
                               reverse("accept_invitation", args=[self.domain, self.get_id]))
        params = {"domain": self.domain, "url": url, "inviter": self.get_inviter().formatted_name}
        text_content = render_to_string("domain/email/domain_invite.txt", params)
        html_content = render_to_string("domain/email/domain_invite.html", params)
        subject = 'Invitation from %s to join CommCareHQ' % self.get_inviter().formatted_name        
        send_HTML_email(subject, self.email, text_content, html_content)

    
    
class HqUserProfile(CouchUserProfile):
    """
    The CoreHq Profile object, which saves the user data in couch along
    with annotating whatever additional fields we need for Hq
    (Right now, none additional are required)
    """
    
    class Meta:
        app_label = 'users'
    
    def __unicode__(self):
        return "%s" % self.user

    def get_couch_user(self):
        return couch_user_from_django_user(self.user)
        
def create_hq_user_from_commcare_registration_info(domain, username, password,
                                                   uuid='', device_id='',
                                                   date='', user_data={},
                                                   **kwargs):
    
    # create django user for the commcare account
    login = create_user(username, password, uuid=uuid)

    # hack the domain into the login too for replication purposes
    couch_user = CommCareUser.get(uuid, db=get_db())
    
    # populate the couch user
    
    couch_user.add_commcare_account(domain, device_id, user_data)

    if date:
        couch_user.created_on = force_to_datetime(date)
    else:
        couch_user.created_on = datetime.utcnow()
    
    couch_user['domains'] = [domain]
    couch_user.save()
    
    return couch_user
    

    
# make sure our signals are loaded
import corehq.apps.users.signals
