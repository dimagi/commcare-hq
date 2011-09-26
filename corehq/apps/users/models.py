"""
couch models go here
"""
from __future__ import absolute_import

from datetime import datetime
import logging

from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string

from couchdbkit.ext.django.schema import *
from couchdbkit.resource import ResourceNotFound
from casexml.apps.case.models import CommCareCase

from casexml.apps.phone.models import User as CaseXMLUser

from corehq.apps.domain.shortcuts import create_user
from corehq.apps.domain.utils import normalize_domain_name
from corehq.apps.reports.models import ReportNotification
from corehq.apps.users.util import normalize_username, user_data_from_registration_form
from couchforms.models import XFormInstance

from dimagi.utils.couch.database import get_db
from dimagi.utils.django.email import send_HTML_email
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.django.database import get_unique_value


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

    ATTRS = (
        'username',
        'first_name',
        'last_name',
        'email',
        'password',
        'is_staff',
        'is_active',
        'is_superuser',
        'last_login',
        'date_joined',
    )


class CouchUser(Document, DjangoUserMixin, UnicodeMixIn):

    """
    A user (for web and commcare)

    """

    base_doc = 'CouchUser'

    device_ids = ListProperty()
    phone_numbers = ListProperty()

    created_on = DateTimeProperty()

#    For now, 'status' is things like:
#        ('auto_created',     'Automatically created from form submission.'),
#        ('phone_registered', 'Registered from phone'),
#        ('site_edited',     'Manually added or edited from the HQ website.'),

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
        return ReportNotification.view("reports/user_notifications", key=self.user_id, include_docs=True).all()

    def delete(self):
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
        super(CouchUser, self).delete() # Call the "real" delete() method.

    def get_django_user(self):
        return User.objects.get(username=self.username)

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
    def all(cls):
        return CouchUser.view("users/by_username", include_docs=True)

    @classmethod
    def by_domain(cls, domain, is_active=True):
        flag = "active" if is_active else "inactive"
        if cls.__name__ == "CouchUser":
            key = [flag, domain]
        else:
            key = [flag, domain, cls.__name__]
        return cls.view("users/by_domain",
            reduce=False,
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
        )

    @classmethod
    def phone_users_by_domain(cls, domain):
        return CouchUser.view("users/phone_users_by_domain",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
        )

    # for synching
    def sync_from_django_user(self, django_user):
        if not django_user:
            django_user = self.get_django_user()
        for attr in DjangoUserMixin.ATTRS:
            setattr(self, attr, getattr(django_user, attr))

    def sync_to_django_user(self):
        try:
            django_user = self.get_django_user()
        except User.DoesNotExist:
            django_user = User(username=self.username)
        for attr in DjangoUserMixin.ATTRS:
            setattr(django_user, attr, getattr(self, attr))
        django_user.DO_NOT_SAVE_COUCH_USER= True
        return django_user

    def sync_from_old_couch_user(self, old_couch_user):
        login = old_couch_user.default_account.login
        self.sync_from_django_user(login)

        for attr in (
            'device_ids',
            'phone_numbers',
            'created_on',
            'status',
        ):
            setattr(self, attr, getattr(old_couch_user, attr))

    @classmethod
    def from_old_couch_user(cls, old_couch_user, copy_id=True):

        if old_couch_user.account_type == "WebAccount":
            couch_user = WebUser()
        else:
            couch_user = CommCareUser()

        couch_user.sync_from_old_couch_user(old_couch_user)

        if old_couch_user.email:
            couch_user.email = old_couch_user.email

        if copy_id:
            couch_user._id = old_couch_user.default_account.login_id

        return couch_user

    @classmethod
    def wrap_correctly(cls, source):
        if source.get('doc_type') == 'CouchUser' and \
                source.has_key('commcare_accounts') and \
                source.has_key('web_accounts'):
            from . import old_couch_user_models
            user_id = old_couch_user_models.CouchUser.wrap(source).default_account.login_id
            return cls.get_by_user_id(user_id)
        else:
            return {
                'WebUser': WebUser,
                'CommCareUser': CommCareUser,
            }[source['doc_type']].wrap(source)

    @classmethod
    def get_by_username(cls, username):
        result = get_db().view('users/by_username', key=username, include_docs=True).one()
        if result:
            return cls.wrap_correctly(result['doc'])
        else:
            return None

    @classmethod
    def get_by_user_id(cls, userID, domain=None):
        couch_user = cls.wrap_correctly(get_db().get(userID))
        if couch_user.doc_type != cls.__name__ and cls.__name__ != "CouchUser":
            raise CouchUser.AccountTypeError()
        if domain:
            if hasattr(couch_user, 'domain'):
                if couch_user.domain != domain and not couch_user.is_superuser:
                    return None
            elif hasattr(couch_user, 'domains'):
                if domain not in couch_user.domains and not couch_user.is_superuser:
                    return None
            else:
                raise CouchUser.AccountTypeError("User %s (%s) has neither domain nor domains" % (
                    couch_user.username,
                    couch_user.user_id
                ))
        return couch_user

    @classmethod
    def from_django_user(cls, django_user):
        couch_user = cls.get_by_username(django_user.username)
        return couch_user

    @classmethod
    def create(cls, domain, username, password, email=None, uuid='', date='', **kwargs):
        django_user = create_user(username, password=password, email=email)
        if uuid:
            couch_user = cls(_id=uuid)
        else:
            couch_user = cls()

        if date:
            couch_user.created_on = force_to_datetime(date)
        else:
            couch_user.created_on = datetime.utcnow()
        couch_user.sync_from_django_user(django_user)
        return couch_user

    def save(self, **params):
        # test no username conflict
        by_username = get_db().view('users/by_username', key=self.username).one()
        if by_username and by_username['id'] != self._id:
            raise self.Inconsistent("CouchUser with username %s already exists" % self.username)
        
        super(CouchUser, self).save(**params)
        if not self.base_doc.endswith("-Deleted"):
            django_user = self.sync_to_django_user()
            django_user.save()

    @classmethod
    def django_user_post_save_signal(cls, sender, django_user, created, **kwargs):
        if hasattr(django_user, 'DO_NOT_SAVE_COUCH_USER'):
            del django_user.DO_NOT_SAVE_COUCH_USER
        else:
            couch_user = cls.from_django_user(django_user)
            if couch_user:
                couch_user.sync_from_django_user(django_user)
                # avoid triggering cyclical sync
                super(CouchUser, couch_user).save()

class CommCareUser(CouchUser):

    domain = StringProperty()
    registering_device_id = StringProperty()
    user_data = DictProperty()

    def sync_from_old_couch_user(self, old_couch_user):
        super(CommCareUser, self).sync_from_old_couch_user(old_couch_user)
        self.domain                 = normalize_domain_name(old_couch_user.default_account.domain)
        self.registering_device_id  = old_couch_user.default_account.registering_device_id
        self.user_data              = old_couch_user.default_account.user_data

    @classmethod
    def create(cls, domain, username, password, email=None, uuid='', date='', **kwargs):
        """
        used to be a function called `create_hq_user_from_commcare_registration_info`

        """
        commcare_user = super(CommCareUser, cls).create(domain, username, password, email, uuid, date, **kwargs)

        device_id = kwargs.get('device_id', '')
        user_data = kwargs.get('user_data', {})

        # populate the couch user
        commcare_user.domain = domain
        commcare_user.device_ids = [device_id]
        commcare_user.registering_device_id = device_id
        commcare_user.user_data = user_data

        commcare_user.save()

        return commcare_user

    @classmethod
    def create_from_xform(cls, xform):
        def get_or_create_safe(username, password, uuid, date, registering_phone_id, domain, user_data, **kwargs):
            # check for uuid conflicts, if one exists, respond with the already-created user
            try:
                conflicting_user = CommCareUser.get_by_user_id(uuid)
                logging.error("Trying to create a new user %s from form %s!  You can't submit multiple registration xmls for the same uuid." % \
                              (uuid, xform.get_id))
                return conflicting_user
            except ResourceNotFound:
                # Desired outcome
                pass
            # we need to check for username conflicts, other issues
            # and make sure we send the appropriate conflict response to the phone
            try:
                username = normalize_username(username, domain)
            except ValidationError:
                raise Exception("Username (%s) is invalid: valid characters include [a-z], "
                                "[0-9], period, underscore, and single quote" % username)
            try:
                User.objects.get(username=username)
            except User.DoesNotExist:
                # Desired outcome
                pass
            else:
                # Come up with a suitable username
                prefix, suffix = username.split("@")
                username = get_unique_value(User.objects, "username", prefix, sep="", suffix="@%s" % suffix)
            return cls.create(domain, username, password,
                uuid=uuid,
                device_id=registering_phone_id,
                date=date,
                user_data=user_data
            )

        # will raise TypeError if xform.form doesn't have all the necessary params
        return get_or_create_safe(
            domain=xform.domain,
            user_data=user_data_from_registration_form(xform),
            **dict([(arg, xform.form[arg]) for arg in (
                'username',
                'password',
                'uuid',
                'date',
                'registering_phone_id'
            )])
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

    def get_forms(self):
        return XFormInstance.view('couchforms/by_user',
            startkey=[self.user_id],
            endkey=[self.user_id, {}],
            reduce=False,
            include_docs=True,
        )

    @property
    def form_count(self):
        result = XFormInstance.view('couchforms/by_user',
            startkey=[self.user_id],
            endkey=[self.user_id, {}],
                group_level=0
        ).one()
        if result:
            return result['value']
        else:
            return 0

    def get_cases(self):
        return CommCareCase.view('case/by_user',
            startkey=[self.user_id],
            endkey=[self.user_id, {}],
            reduce=False,
            include_docs=True
        )

    @property
    def case_count(self):
        result = CommCareCase.view('case/by_user',
            startkey=[self.user_id],
            endkey=[self.user_id, {}],
            group_level=0
        ).one()
        if result:
            return result['value']
        else:
            return 0

    def retire(self):
        suffix = '-Deleted'
        # doc_type remains the same, since the views use base_doc instead
        if not self.base_doc.endswith(suffix):
            self.base_doc += suffix
        for form in self.get_forms():
            form.doc_type += suffix
            form.save()
        for case in self.get_cases():
            case.doc_type += suffix
            case.save()
        try:
            django_user = self.get_django_user()
        except User.DoesNotExist:
            pass
        else:
            django_user.delete()
            
        self.save()
        
class WebUser(CouchUser):
    domains = StringListProperty()
    domain_memberships = SchemaListProperty(DomainMembership)

    def sync_from_old_couch_user(self, old_couch_user):
        super(WebUser, self).sync_from_old_couch_user(old_couch_user)
        for dm in old_couch_user.web_account.domain_memberships:
            dm.domain = normalize_domain_name(dm.domain)
            self.domain_memberships.append(dm)
            self.domains.append(dm.domain)

    @classmethod
    def create(cls, domain, username, password, email=None, uuid='', date='', **kwargs):
        web_user = super(WebUser, cls).create(domain, username, password, email, uuid, date, **kwargs)
        if domain:
            web_user.add_domain_membership(domain, **kwargs)
        web_user.save()
        return web_user

    def is_commcare_user(self):
        return False

    def get_domain_membership(self, domain):
        domain_membership = None
        try:
            for d in self.domain_memberships:
                if d.domain == domain:
                    domain_membership = d
                    if domain not in self.domains:
                        raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
            if domain in self.domains:
                raise self.Inconsistent("Domain '%s' is in domain but not in domain_memberships" % domain)
        except self.Inconsistent as e:
            logging.warning(e)
            self.domains = [d.domain for d in self.domain_memberships]
        return domain_membership

    def add_domain_membership(self, domain, **kwargs):
        for d in self.domain_memberships:
            if d.domain == domain:
                if domain not in self.domains:
                    raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
                return
        self.domain_memberships.append(DomainMembership(domain=domain,
                                                        **kwargs))
        self.domains.append(domain)

    def delete_domain_membership(self, domain):
        for i, dm in enumerate(self.domain_memberships):
            if dm.domain == domain:
                del self.domain_memberships[i]
                break
        for i, domain_name in enumerate(self.domains):
            if domain_name == domain:
                del self.domains[i]
                break
    
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

    def get_domains(self):
        domains = [dm.domain for dm in self.domain_memberships]
        if set(domains) == set(self.domains):
            return domains
        else:
            raise self.Inconsistent("domains and domain_memberships out of sync")

    def is_member_of(self, domain_qs):
        if isinstance(domain_qs, basestring):
            return domain_qs in self.get_domains() or self.is_superuser
        membership_count = domain_qs.filter(name__in=self.get_domains()).count()
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

#
# Django  models go here
#
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
        if self._inviter is None:
            self._inviter = CouchUser.get_by_user_id(self.invited_by)
            if self._inviter.user_id != self.invited_by:
                self.invited_by = self._inviter.user_id
                self.save()
        return self._inviter

    def send_activation_email(self):

        url = "http://%s%s" % (Site.objects.get_current().domain,
                               reverse("accept_invitation", args=[self.domain, self.get_id]))
        params = {"domain": self.domain, "url": url, "inviter": self.get_inviter().formatted_name}
        text_content = render_to_string("domain/email/domain_invite.txt", params)
        html_content = render_to_string("domain/email/domain_invite.html", params)
        subject = 'Invitation from %s to join CommCareHQ' % self.get_inviter().formatted_name
        send_HTML_email(subject, self.email, text_content, html_content)

from .signals import *
