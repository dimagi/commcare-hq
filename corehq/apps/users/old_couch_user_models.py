from __future__ import absolute_import

from datetime import datetime
from django.contrib.auth.models import User
from dimagi.utils.couch.database import get_db
from couchdbkit.ext.django.schema import *
from corehq.apps.domain.models import Domain
from corehq.apps.users.util import django_user_from_couch_id
from dimagi.utils.mixins import UnicodeMixIn
from corehq.apps.reports.models import ReportNotification
from casexml.apps.phone.models import User as CaseXMLUser
from corehq.apps.users.exceptions import NoAccountException

from corehq.apps.users.models import Permissions, DomainMembership, _get_default, _add_to_list

class Login(DocumentSchema):
    username = StringProperty()
    password = StringProperty()

class Account(Document):
    # the UUID which is also the login doc's _id
    login_id = StringProperty()

    @property
    def login(self):
        try:
            return Login.wrap(get_db().get(self.login_id)['django_user'])
        except:
            return None


    def username_html(self):
        username = self.login['username']
        html = "<span class='user_username'>%s</span>" % username
        return html

    class Meta:
        app_label = 'users'

class CommCareAccount(Account):
    """
    This is the information associated with a
    particular commcare user. Right now, we
    associate one commcare user to one web user
    (with multiple domain logins, phones, SIMS)
    but we could always extend to multiple commcare
    users if desired later.
    """

    registering_device_id = StringProperty()
    user_data = DictProperty()
    domain = StringProperty()

    def username_html(self):
        username = self.login['username']
        if '@' in username:
            html = "<span class='user_username'>%s</span><span class='user_domainname'>@%s</span>" % \
                   tuple(username.split('@'))
        else:
            html = "<span class='user_username'>%s</span>" % username
        return html

    class Meta:
        app_label = 'users'

    @classmethod
    def get_by_userID(cls, userID):
        return cls.view('users/commcare_users_by_login_id', key=userID).one()

class WebAccount(Account):
    domain_memberships = SchemaListProperty(DomainMembership)

    class Meta:
        app_label = 'users'

class CouchUser(Document, UnicodeMixIn):

    """
    a user (for web+commcare+sms)
    can be associated with multiple username/password/login tuples
    can be associated with multiple phone numbers/SIM cards
    can be associated with multiple phones/device IDs
    """
    # not used e.g. when user is only a commcare user

    first_name = StringProperty()
    last_name = StringProperty()
    email = StringProperty()

    # the various commcare accounts associated with this user
    web_account = SchemaProperty(WebAccount)
    commcare_accounts = SchemaListProperty(CommCareAccount)

    device_ids = ListProperty()
    phone_numbers = ListProperty()

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



    """This is the future intended API"""

    @property
    def account_type(self):
        if self.web_account.login_id:
            return "WebAccount"
        else:
            return "CommCareAccount"

    @property
    def username(self):
        if self.default_account is not None:
            username = self._doc.get('username')
            if not username:
                username = self.default_account.login.username
                self._doc['username'] = username
                self.save()
            return username

        raise NoAccountException("No account found for %s" % self)

    @username.setter
    def username(self, value):
        pass


    @property
    def raw_username(self):
        if self.account_type == "CommCareAccount":
            return self.username.split("@")[0]
        else:
            return self.username
    @property
    def userID(self):
        return self.default_account.login_id

    user_id = userID

    @property
    def password(self):
        return self.default_account.login.password

    @property
    def date_joined(self):
        return self.default_account.login.date_joined

    @property
    def user_data(self):
        try:
            return self.default_account.user_data
        except KeyError:
            return {}

    @property
    def is_superuser(self):
        return self.default_account.login.is_superuser

    class Meta:
        app_label = 'users'

    def __unicode__(self):
        return "couch user %s" % self.get_id

    @property
    def default_django_user(self):
        login_id = ""
        # first choice: web user login
        if self.web_account.login_id:
            login_id = self.web_account.login_id
        # second choice: latest registered commcare account
        elif self.commcare_accounts:
            login_id = _get_default(self.commcare_accounts).login_id
        else:
            raise User.DoesNotExist("This couch user doesn't have a linked django login!")
        return django_user_from_couch_id(login_id)


    def get_email(self):
        return self.email or self.default_django_user.email
    @property
    def formatted_name(self):
        return "%s %s" % (self.first_name, self.last_name)

    @property
    def default_account(self):
        if self.web_account.login_id:
            return self.web_account
        else:
            return self.default_commcare_account

    def is_commcare_user(self):
        return self.account_type == "CommCareAccount"

    def to_casexml_user(self):
        return CaseXMLUser(user_id=self.userID,
                           username=self.raw_username,
                           password=self.password,
                           date_joined=self.date_joined,
                           user_data=self.user_data)

    def save(self, *args, **kwargs):
        # Call the "real" save() method.
        super(CouchUser, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
        super(CouchUser, self).delete(*args, **kwargs) # Call the "real" delete() method.

    def add_django_user(self, username, password, **kwargs):
        # DO NOT implement this. It will create an endless loop.
        raise NotImplementedError

    def get_django_user(self):
        return User.objects.get(username=self.web_account.login_id)

    def get_domain_membership(self, domain):
        for d in self.web_account.domain_memberships:
            if d.domain == domain:
                return d

    def add_domain_membership(self, domain, **kwargs):
        for d in self.web_account.domain_memberships:
            if d.domain == domain:
                # membership already exists
                return
        self.web_account.domain_memberships.append(DomainMembership(domain=domain,
                                                        **kwargs))

    def is_domain_admin(self, domain=None):
        if not domain:
            # hack for template
            if hasattr(self, 'current_domain'):
                # this is a hack needed because we can't pass parameters from views
                domain = self.current_domain
            else:
                return False # no domain, no admin
        if self.web_account.login.is_superuser:
            return True
        dm = self.get_domain_membership(domain)
        if dm:
            return dm.is_admin
        else:
            return False

    @property
    def domain_names(self):
        return [dm.domain for dm in self.web_account.domain_memberships]

    def get_active_domains(self):
        domain_names = self.domain_names
        return Domain.view("domain/domains",
                            keys=domain_names,
                            reduce=False,
                            include_docs=True).all()

    def is_member_of(self, domain_qs):
        if isinstance(domain_qs, basestring):
            return domain_qs in self.domain_names or self.is_superuser
        membership_count = domain_qs.filter(name__in=self.domain_names).count()
        if membership_count > 0:
            return True
        return False

    def add_commcare_account(self, django_user, domain, device_id, user_data={}, **kwargs):
        """
        Adds a commcare account to this.
        """
        commcare_account = CommCareAccount(login_id=django_user.get_profile()._id,
                                           domain=domain,
                                           registering_device_id=device_id,
                                           user_data=user_data,
                                           **kwargs)

        self.commcare_accounts = _add_to_list(self.commcare_accounts, commcare_account, default=True)

    @property
    def default_commcare_account(self, domain=None):
        if hasattr(self, 'current_domain'):
            # this is a hack needed because we can't pass parameters from views
            domain = self.current_domain
        if domain:
            for account in self.commcare_accounts:
                if account.domain == domain:
                    return account
        else:
            return _get_default(self.commcare_accounts)

    def link_commcare_account(self, domain, from_couch_user_id, commcare_login_id, **kwargs):
        from_couch_user = CouchUser.get(from_couch_user_id)
        for i in range(0, len(from_couch_user.commcare_accounts)):
            if from_couch_user.commcare_accounts[i].login_id == commcare_login_id:
                # this generates a 'document update conflict'. why?
                self.commcare_accounts.append(from_couch_user.commcare_accounts[i])
                self.save()
                del from_couch_user.commcare_accounts[i]
                from_couch_user.save()
                return

    def unlink_commcare_account(self, domain, commcare_user_index, **kwargs):
        commcare_user_index = int(commcare_user_index)
        c = CouchUser()
        c.created_on = datetime.now()
        original = self.commcare_accounts[commcare_user_index]
        c.commcare_accounts.append(original)
        c.status = 'unlinked from %s' % self._id
        c.save()
        # is there a more atomic way to do this?
        del self.commcare_accounts[commcare_user_index]
        self.save()

    def add_device_id(self, device_id, default=False, **kwargs):
        """ Don't add phone devices if they already exist """
        self.device_ids = _add_to_list(self.device_ids, device_id, default)

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

    @classmethod
    def from_web_user(cls, user):
        login_id = user.get_profile()._id
        assert(len(cls.view("users/couch_users_by_django_profile_id", include_docs=True, key=login_id)) == 0)
        couch_user = cls()
        couch_user.web_account.login_id = login_id
        couch_user.first_name = user.first_name
        couch_user.last_name = user.last_name
        couch_user.email = user.email
        return couch_user

    # Couch view wrappers
    @classmethod
    def phone_users_by_domain(cls, domain):
        return CouchUser.view("users/phone_users_by_domain",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
        )
    @classmethod
    def commcare_users_by_domain(cls, domain):
        return CouchUser.view("users/commcare_users_by_domain",
            reduce=False,
            key=domain,
            include_docs=True,
        )

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
