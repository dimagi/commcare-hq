"""
couch models go here
"""
from __future__ import absolute_import

from datetime import datetime
import logging
import re
from django.utils import html, safestring
from restkit.errors import NoMoreData
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.make_uuid import random_hex
from dimagi.utils.modules import to_function

from django.conf import settings
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
from corehq.apps.reports.models import ReportNotification, HQUserType
from corehq.apps.users.util import normalize_username, user_data_from_registration_form, format_username, raw_username, cc_user_domain
from corehq.apps.users.xml import group_fixture
from corehq.apps.sms.mixin import CommCareMobileContactMixin
from couchforms.models import XFormInstance

from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.undo import DeleteRecord, DELETED_SUFFIX
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

class OldPermissions(object):
    EDIT_WEB_USERS = 'edit-users'
    EDIT_COMMCARE_USERS = 'edit-commcare-users'
    EDIT_DATA = 'edit-data'
    EDIT_APPS = 'edit-apps'

    VIEW_REPORTS = 'view-reports'
    VIEW_REPORT = 'view-report'

    AVAILABLE_PERMISSIONS = [EDIT_DATA, EDIT_WEB_USERS, EDIT_COMMCARE_USERS, EDIT_APPS, VIEW_REPORTS, VIEW_REPORT]
    perms = 'EDIT_DATA, EDIT_WEB_USERS, EDIT_COMMCARE_USERS, EDIT_APPS, VIEW_REPORTS, VIEW_REPORT'.split(', ')
    old_to_new = dict([(locals()[attr], attr.lower()) for attr in perms])

    @classmethod
    def to_new(cls, old_permission):
        return cls.old_to_new[old_permission]



class OldRoles(object):
    ROLES = (
        ('edit-apps', 'App Editor', set([OldPermissions.EDIT_APPS])),
        ('field-implementer', 'Field Implementer', set([OldPermissions.EDIT_COMMCARE_USERS])),
        ('read-only', 'Read Only', set([]))
    )

    @classmethod
    def get_role_labels(cls):
        return tuple([('admin', 'Admin')] + [(key, label) for (key, label, _) in cls.ROLES])

    @classmethod
    def get_role_mapping(cls):
        return dict([(key, perms) for (key, _, perms) in cls.ROLES])

class Permissions(DocumentSchema):
    edit_web_users = BooleanProperty(default=False)
    edit_commcare_users = BooleanProperty(default=False)
    edit_data = BooleanProperty(default=False)
    edit_apps = BooleanProperty(default=False)

    view_reports = BooleanProperty(default=False)
    view_report_list = StringListProperty(default=[])

    def view_report(self, report, value=None):
        """Both a getter (when value=None) and setter (when value=True|False)"""

        if value is None:
            return self.view_reports or report in self.view_report_list
        else:
            if value:
                if report not in self.view_report_list:
                    self.view_report_list.append(report)
            else:
                try:
                    self.view_report_list.remove(report)
                except ValueError:
                    pass

    def has(self, permission, data=None):
        if data:
            return getattr(self, permission)(data)
        else:
            return getattr(self, permission)

    def set(self, permission, value, data=None):
        if self.has(permission, data) == value:
            return
        if data:
            getattr(self, permission)(data, value)
        else:
            setattr(self, permission, value)

    def _getattr(self, name):
        a = getattr(self, name)
        if isinstance(a, list):
            a = set(a)
        return a

    def _setattr(self, name, value):
        if isinstance(value, set):
            value = list(value)
        setattr(self, name, value)

    def __or__(self, other):
        permissions = Permissions()
        for name in permissions.properties():
            permissions._setattr(name, self._getattr(name) | other._getattr(name))
        return permissions

    def __eq__(self, other):
        for name in self.properties():
            if self._getattr(name) != other._getattr(name):
                return False
        return True

    @classmethod
    def max(cls):
        return Permissions(
            edit_web_users=True,
            edit_commcare_users=True,
            edit_data=True,
            edit_apps=True,
            view_reports=True,
        )

class UserRole(Document):
    domain = StringProperty()
    name = StringProperty()
    permissions = SchemaProperty(Permissions)

    def get_qualified_id(self):
        return 'user-role:%s' % self.get_id

    @classmethod
    def by_domain(cls, domain):
        return cls.view('users/roles_by_domain',
            key=domain,
            include_docs=True,
            reduce=False,
        )

    @classmethod
    def get_or_create_with_permissions(cls, domain, permissions, name=None):
        if isinstance(permissions, dict):
            permissions = Permissions.wrap(permissions)
        roles = cls.by_domain(domain)
        # try to get a matching role from the db
        for role in roles:
            if role.permissions == permissions:
                return role
        # otherwise create it
        def get_name():
            if name:
                return name
            elif permissions == Permissions():
                return "Read Only (No Reports)"
            elif permissions == Permissions(edit_apps=True, view_reports=True):
                return "App Editor"
            elif permissions == Permissions(view_reports=True):
                return "Read Only"
            elif permissions == Permissions(edit_commcare_users=True, view_reports=True):
                return "Field Implementer"
        role = cls(domain=domain, permissions=permissions, name=get_name())
        role.save()
        return role

    @classmethod
    def init_domain_with_presets(cls, domain):
        cls.get_or_create_with_permissions(domain, Permissions(edit_apps=True, view_reports=True), 'App Editor')
        cls.get_or_create_with_permissions(domain, Permissions(edit_commcare_users=True, view_reports=True), 'Field Implementer')
        cls.get_or_create_with_permissions(domain, Permissions(view_reports=True), 'Read Only')

    @classmethod
    def get_default(cls, domain=None):
        return cls(permissions=Permissions(), domain=domain, name=None)

    @classmethod
    def role_choices(cls, domain):
        return [(role.get_qualified_id(), role.name or '(No Name)') for role in [AdminUserRole(domain=domain)] + list(cls.by_domain(domain))]
    
    @classmethod
    def commcareuser_role_choices(cls, domain):
        return [('none','(none)')] + [(role.get_qualified_id(), role.name or '(No Name)') for role in list(cls.by_domain(domain))]

PERMISSIONS_PRESETS = {
    'edit-apps': {'name': 'App Editor', 'permissions': Permissions(edit_apps=True, view_reports=True)},
    'field-implementer': {'name': 'Field Implementer', 'permissions': Permissions(edit_commcare_users=True, view_reports=True)},
    'read-only': {'name': 'Read Only', 'permissions': Permissions(view_reports=True)},
    'no-permissions': {'name': 'Read Only', 'permissions': Permissions(view_reports=True)},
}

class AdminUserRole(UserRole):
    def __init__(self, domain):
        super(AdminUserRole, self).__init__(domain=domain, name='Admin', permissions=Permissions.max())
    def get_qualified_id(self):
        return 'admin'

class DomainMembershipError(Exception):
    pass

class DomainMembership(DocumentSchema):
    """
    Each user can have multiple accounts on the
    web domain. This is primarily for Dimagi staff.
    """

    domain = StringProperty()
    is_admin = BooleanProperty(default=False)
    # old permissions
    # permissions = StringListProperty()
    # permissions_data = DictProperty()
    last_login = DateTimeProperty()
    date_joined = DateTimeProperty()
    timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    override_global_tz = BooleanProperty(default=False)

    role_id = StringProperty()

    @property
    def permissions(self):
        if self.role:
            return self.role.permissions
        else:
            return Permissions()

    @classmethod
    def wrap(cls, data):
        if data.get('subject'):
            data['domain'] = data['subject']
            del data['subject']
        # Do a just-in-time conversion of old permissions
        old_permissions = data.get('permissions')
        if old_permissions is not None:
            del data['permissions']
            if data.has_key('permissions_data'):
                permissions_data = data['permissions_data']
                del data['permissions_data']
            else:
                permissions_data = {}
            if not data['is_admin']:
                view_report_list = permissions_data.get('view-report')
                custom_permissions = {}
                for old_permission in old_permissions:
                    if old_permission == 'view-report':
                        continue
                    new_permission = OldPermissions.to_new(old_permission)
                    custom_permissions[new_permission] = True

                if not view_report_list:
                    # Anyone whose report permissions haven't been explicitly taken away/reduced
                    # should be able to see reports by default
                    custom_permissions['view_reports'] = True
                else:
                    custom_permissions['view_report_list'] = view_report_list


                self = super(DomainMembership, cls).wrap(data)
                self.role_id = UserRole.get_or_create_with_permissions(self.domain, custom_permissions).get_id
                return self
        return super(DomainMembership, cls).wrap(data)

    @property
    def role(self):
        if self.is_admin:
            return AdminUserRole(self.domain)
        elif self.role_id:
            return UserRole.get(self.role_id)
        else:
            return None

    def has_permission(self, permission, data=None):
        return self.is_admin or self.permissions.has(permission, data)

    def viewable_reports(self):
        return self.permissions.view_report_list

    class Meta:
        app_label = 'users'

class CustomDomainMembership(DomainMembership):
    custom_role = SchemaProperty(UserRole)

    @property
    def role(self):
        if self.is_admin:
            return AdminUserRole(self.domain)
        else:
            return self.custom_role

    def set_permission(self, permission, value, data=None):
        self.custom_role.domain = self.domain
        self.custom_role.permissions.set(permission, value, data)



class AuthorizableMixin(DocumentSchema):
    domains = StringListProperty()
    domain_memberships = SchemaListProperty(DomainMembership)

    def is_global_admin(self):
        # subclasses to override if they want this functionality
        return False

    def get_domain_membership(self, domain):
        domain_membership = None
        try:
            for d in self.domain_memberships:
                if d.domain == domain:
                    domain_membership = d
                    if domain not in self.domains:
                        raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
            if not domain_membership and domain in self.domains:
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

        domain_obj = Domain.get_by_name(domain)
        if not domain_obj:
            domain_obj = Domain(is_active=True, name=domain, date_created=datetime.utcnow())
            domain_obj.save()

        if kwargs.get('timezone'):
            domain_membership = DomainMembership(domain=domain, **kwargs)
        else:
            domain_membership = DomainMembership(domain=domain,
                                            timezone=domain_obj.default_timezone,
                                            **kwargs)
        self.domain_memberships.append(domain_membership)
        self.domains.append(domain)

    def delete_domain_membership(self, domain, create_record=False):
        for i, dm in enumerate(self.domain_memberships):
            if dm.domain == domain:
                if create_record:
                    record = RemoveWebUserRecord(
                        domain=domain,
                        user_id=self.user_id,
                        domain_membership=dm,
                    )
                del self.domain_memberships[i]
                break
        for i, domain_name in enumerate(self.domains):
            if domain_name == domain:
                del self.domains[i]
                break
        if create_record:
            record.save()
            return record

    def is_domain_admin(self, domain=None):
        if not domain:
            # hack for template
            if hasattr(self, 'current_domain'):
                # this is a hack needed because we can't pass parameters from views
                domain = self.current_domain
            else:
                return False # no domain, no admin
        if self.is_global_admin():
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

    def has_permission(self, domain, permission, data=None):
        # is_admin is the same as having all the permissions set
        if self.is_global_admin():
            return True
        elif self.is_domain_admin(domain):
            return True

        dm = self.get_domain_membership(domain)
        if dm:
            return dm.has_permission(permission, data)
        else:
            return False

    def is_member_of(self, domain_qs):
        try:
            return self.is_global_admin() or domain_qs.name in self.get_domains()
        except Exception:
            return self.is_global_admin() or domain_qs in self.get_domains()

    def get_role(self, domain=None):
        """
        Get the role object for this user

        """
        if domain is None:
            # default to current_domain for django templates
            if hasattr(self, 'current_domain'):
                domain = self.current_domain
            else:
                domain = None

        if self.is_global_admin():
            return AdminUserRole(domain=domain)
        if self.is_member_of(domain): #need to have a way of seeing is_member_of
            return self.get_domain_membership(domain).role
        else:
            raise DomainMembershipError()

    def set_role(self, domain, role_qualified_id):
        """
        role_qualified_id is either 'admin' 'user-role:[id]'
        """
        dm = self.get_domain_membership(domain)
        dm.is_admin = False
        if role_qualified_id == "admin":
            dm.is_admin = True
        elif role_qualified_id.startswith('user-role:'):
            dm.role_id = role_qualified_id[len('user-role:'):]
        elif role_qualified_id in PERMISSIONS_PRESETS:
            preset = PERMISSIONS_PRESETS[role_qualified_id]
            dm.role_id = UserRole.get_or_create_with_permissions(domain, preset['permissions'], preset['name']).get_id
        else:
            raise Exception("role_qualified_id is %r" % role_qualified_id)

    def role_label(self, domain=None):
#        import pdb
#        pdb.set_trace()
        if not domain:
            try:
                domain = self.current_domain
            except (AttributeError, KeyError):
                return None
        try:
            return self.get_role(domain).name
        except TypeError:
            return "Unknown User"
        except DomainMembershipError:
            return "Unauthorized User"
        except Exception:
            return None

class LowercaseStringProperty(StringProperty):
    """
    Make sure that the string is always lowercase'd
    """
    def _adjust_value(self, value):
        if value is not None:
            return value.lower()

#    def __set__(self, instance, value):
#        return super(LowercaseStringProperty, self).__set__(instance, self._adjust_value(value))

#    def __property_init__(self, instance, value):
#        return super(LowercaseStringProperty, self).__property_init__(instance, self._adjust_value(value))

    def to_json(self, value):
        return super(LowercaseStringProperty, self).to_json(self._adjust_value(value))



class DjangoUserMixin(DocumentSchema):
    username = LowercaseStringProperty()
    first_name = StringProperty()
    last_name = StringProperty()
    email = LowercaseStringProperty()
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

    def set_password(self, raw_password):
        dummy = User()
        dummy.set_password(raw_password)
        self.password = dummy.password

    def check_password(self, password):
        """ Currently just for debugging"""
        dummy = User()
        dummy.password = self.password
        return dummy.check_password(password)

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
    language = StringProperty()

    _user = None
    _user_checked = False

    class AccountTypeError(Exception):
        pass

    class Inconsistent(Exception):
        pass

    class InvalidID(Exception):
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
        return "%s %s" % (self.__class__.__name__, self.get_id)

    def __getattr__(self, item):
        if item == 'current_domain':
            return None
        super(CouchUser, self).__getattr__(item)

    def get_email(self):
        return self.email

    @property
    def full_name(self):
        return ("%s %s" % (self.first_name, self.last_name)).strip()

    formatted_name = full_name
    name = full_name

    def set_full_name(self, full_name):
        data = full_name.split()
        self.first_name = data.pop(0)
        self.last_name = ' '.join(data)

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
        return User.objects.get(username__iexact=self.username)

    def add_phone_number(self, phone_number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(phone_number, basestring):
            phone_number = str(phone_number)
        self.phone_numbers = _add_to_list(self.phone_numbers, phone_number, default)

    @property
    def default_phone_number(self):
        return _get_default(self.phone_numbers)
    phone_number = default_phone_number

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
        ).all()

    @classmethod
    def phone_users_by_domain(cls, domain):
        return CouchUser.view("users/phone_users_by_domain",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
        )

    def is_previewer(self):
        try:
            from django.conf.settings import PREVIEWER_RE
        except ImportError:
            return self.is_superuser
        else:
            return self.is_superuser or re.compile(PREVIEWER_RE).match(self.username)

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
                'FakeUser': FakeUser,
            }[source['doc_type']].wrap(source)

    @classmethod
    def get_by_username(cls, username):
        try:
            result = get_db().view('users/by_username', key=username, include_docs=True)
            result = result.one()
        except NoMoreData:
            logging.exception('called get_by_username(%r) and it failed pretty bad' % username)
            raise
        if result:
            return cls.wrap_correctly(result['doc'])
        else:
            return None

    @classmethod
    def get_by_default_phone(cls, phone_number):
        result = get_db().view('users/by_default_phone', key=phone_number, include_docs=True).one()
        if result:
            return cls.wrap_correctly(result['doc'])
        else:
            return None

    def is_global_admin(self):
        return False

    def is_member_of(self, domain_qs):
        """
        takes either a domain name or a domain object and returns whether the user is part of that domain
        either natively or through a team
        """
        try:
            return domain_qs.name in self.get_domains() or self.is_global_admin()
        except Exception:
            return domain_qs in self.get_domains() or self.is_global_admin()

    @classmethod
    def get_by_user_id(cls, userID, domain=None):
        """
        if domain is given, checks to make sure the user is a member of that domain
        returns None if there's no user found or if the domain check fails

        """
        try:
            couch_user = cls.wrap_correctly(get_db().get(userID))
        except ResourceNotFound:
            return None
        if couch_user.doc_type != cls.__name__ and cls.__name__ != "CouchUser":
            raise CouchUser.AccountTypeError()
        if domain:
            if not couch_user.is_member_of(domain):
                return None
        return couch_user

    @classmethod
    def from_django_user(cls, django_user):
        return cls.get_by_username(django_user.username)

    @classmethod
    def create(cls, domain, username, password, email=None, uuid='', date='', **kwargs):
        django_user = create_user(username, password=password, email=email)
        if uuid:
            if not re.match(r'[\w-]+', uuid):
                raise cls.InvalidID('invalid id %r' % uuid)
            couch_user = cls(_id=uuid)
        else:
            couch_user = cls()

        if date:
            couch_user.created_on = force_to_datetime(date)
        else:
            couch_user.created_on = datetime.utcnow()
        couch_user.sync_from_django_user(django_user)
        return couch_user

    def change_username(self, username):
        if username == self.username:
            return

        if User.objects.filter(username=username).exists():
            raise self.Inconsistent("User with username %s already exists" % self.username)

        django_user = self.get_django_user()
        django_user.DO_NOT_SAVE_COUCH_USER = True
        django_user.username = username
        django_user.save()
        self.username = username
        self.save()


    def save(self, **params):
        # test no username conflict
        by_username = get_db().view('users/by_username', key=self.username).one()
        if by_username and by_username['id'] != self._id:
            raise self.Inconsistent("CouchUser with username %s already exists" % self.username)

        super(CouchUser, self).save(**params)
        if not self.base_doc.endswith(DELETED_SUFFIX):
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

    def is_deleted(self):
        return self.base_doc.endswith(DELETED_SUFFIX)

    def get_viewable_reports(self, domain=None, name=True):
        try:
            domain = domain or self.current_domain
        except AttributeError:
            domain = None
        try:
            if self.is_commcare_user():
                role = self.get_role(domain)
                if role is None:
                    models = []
                else:
                    models = role.permissions.view_report_list
            else:
                models = self.get_domain_membership(domain).viewable_reports()
            
            if name:
                return [to_function(m).name for m in models]
            else:
                return models
        except AttributeError:
            return []

    def has_permission(self, domain, permission, data=None):
        """To be overridden by subclasses"""
        return False

    def __getattr__(self, item):
        if item.startswith('can_'):
            perm = item[len('can_'):]
            if perm:
                def fn(domain=None, data=None):
                    try:
                        domain = domain or self.current_domain
                    except AttributeError:
                        domain = None
                    return self.has_permission(domain, perm, data)
                fn.__name__ = item
                return fn
        return super(CouchUser, self).__getattr__(item)


class CommCareUser(CouchUser, CommCareMobileContactMixin):

    domain = StringProperty()
    registering_device_id = StringProperty()
    user_data = DictProperty()
    role_id = StringProperty()

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

    @property
    def filter_flag(self):
        return HQUserType.REGISTERED

    @property
    def username_in_report(self):
        def parts():
            yield u'%s' % html.escape(self.raw_username)
            if self.full_name:
                yield u' "%s" ' % html.escape(self.full_name)

        return safestring.mark_safe(''.join(parts()))

    @classmethod
    def create_or_update_from_xform(cls, xform):
        # if we have 1,000,000 users with the same name in a domain
        # then we have bigger problems then duplicate user accounts
        MAX_DUPLICATE_USERS = 1000000

        def create_or_update_safe(username, password, uuid, date, registering_phone_id, domain, user_data, **kwargs):
            # check for uuid conflicts, if one exists, respond with the already-created user
            conflicting_user = CommCareUser.get_by_user_id(uuid)

            # we need to check for username conflicts, other issues
            # and make sure we send the appropriate conflict response to the phone
            try:
                username = normalize_username(username, domain)
            except ValidationError:
                raise Exception("Username (%s) is invalid: valid characters include [a-z], "
                                "[0-9], period, underscore, and single quote" % username)

            if conflicting_user:
                # try to update. If there are username conflicts, we have to resolve them
                if conflicting_user.domain != domain:
                    raise Exception("Found a conflicting user in another domain. This is not allowed!")

                saved = False
                to_append = 2
                prefix, suffix = username.split("@")
                while not saved and to_append < MAX_DUPLICATE_USERS:
                    try:
                        conflicting_user.change_username(username)
                        conflicting_user.password = password
                        conflicting_user.date = date
                        conflicting_user.device_id = registering_phone_id
                        conflicting_user.user_data = user_data
                        conflicting_user.save()
                        saved = True
                    except CouchUser.Inconsistent:
                        username = "%(pref)s%(count)s@%(suff)s" % {
                                     "pref": prefix, "count": to_append,
                                     "suff": suffix}
                        to_append = to_append + 1
                if not saved:
                    raise Exception("There are over 1,000,000 users with that base name in your domain. REALLY?!? REALLY?!?!")
                return (conflicting_user, False)

            try:
                User.objects.get(username=username)
            except User.DoesNotExist:
                # Desired outcome
                pass
            else:
                # Come up with a suitable username
                prefix, suffix = username.split("@")
                username = get_unique_value(User.objects, "username", prefix, sep="", suffix="@%s" % suffix)
            couch_user = cls.create(domain, username, password,
                uuid=uuid,
                device_id=registering_phone_id,
                date=date,
                user_data=user_data
            )
            return (couch_user, True)

        # will raise TypeError if xform.form doesn't have all the necessary params
        return create_or_update_safe(
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

    @classmethod
    def cannot_share(cls, domain):
        return [user for user in cls.by_domain(domain) if len(user.get_case_sharing_groups()) != 1]

    def is_commcare_user(self):
        return True

    def is_web_user(self):
        return False

    def get_domains(self):
        return [self.domain]

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
        user = CaseXMLUser(user_id=self.userID,
                           username=self.raw_username,
                           password=self.password,
                           date_joined=self.date_joined,
                           user_data=self.user_data)

        def get_owner_ids():
            return self.get_owner_ids()
        user.get_owner_ids = get_owner_ids
        user._hq_user = self # don't tell anyone that we snuck this here
        return user

    def get_forms(self, deleted=False, wrap=True):
        if deleted:
            view_name = 'users/deleted_forms_by_user'
        else:
            view_name = 'couchforms/by_user'

        return XFormInstance.view(view_name,
            startkey=[self.user_id],
            endkey=[self.user_id, {}],
            reduce=False,
            include_docs=wrap,
            wrapper=None if wrap else lambda x: x['id']
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

    def get_cases(self, deleted=False, last_submitter=False):
        if deleted:
            view_name = 'users/deleted_cases_by_user'
        elif last_submitter:
            view_name = 'case/by_user'
        else:
            view_name = 'case/by_owner'

        return CommCareCase.view(view_name,
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

    def get_owner_ids(self):
        from corehq.apps.groups.models import Group

        owner_ids = [self.user_id]
        owner_ids.extend(Group.by_user(self, wrap=False))

        return owner_ids

    def retire(self):
        suffix = DELETED_SUFFIX
        deletion_id = random_hex()
        # doc_type remains the same, since the views use base_doc instead
        if not self.base_doc.endswith(suffix):
            self.base_doc += suffix
            self['-deletion_id'] = deletion_id
        for form in self.get_forms():
            form.doc_type += suffix
            form['-deletion_id'] = deletion_id
            form.save()
        for case in self.get_cases():
            case.doc_type += suffix
            case['-deletion_id'] = deletion_id
            case.save()

        try:
            django_user = self.get_django_user()
        except User.DoesNotExist:
            pass
        else:
            django_user.delete()
        self.save()

    def unretire(self):
        def chop_suffix(string, suffix=DELETED_SUFFIX):
            if string.endswith(suffix):
                return string[:-len(suffix)]
            else:
                return string
        self.base_doc = chop_suffix(self.base_doc)
        for form in self.get_forms(deleted=True):
            form.doc_type = chop_suffix(form.doc_type)
            form.save()
        for case in self.get_cases(deleted=True):
            case.doc_type = chop_suffix(case.doc_type)
            case.save()
        self.save()

    def transfer_to_domain(self, domain, app_id):
        username = format_username(raw_username(self.username), domain)
        self.change_username(username)
        self.domain = domain
        for form in self.get_forms():
            form.domain = domain
            form.app_id = app_id
            form.save()
        for case in self.get_cases():
            case.domain = domain
            case.save()
        self.save()

    def get_group_fixture(self):
        return group_fixture(self.get_case_sharing_groups(), self)

    @memoized
    def get_case_sharing_groups(self):
        from corehq.apps.groups.models import Group
        return [group for group in Group.by_user(self) if group.case_sharing]

    @classmethod
    def cannot_share(cls, domain):
        return [user for user in cls.by_domain(domain) if len(user.get_case_sharing_groups()) != 1]

    def get_group_ids(self):
        from corehq.apps.groups.models import Group
        return Group.by_user(self, wrap=False)

    def get_time_zone(self):
        try:
            time_zone = self.user_data["time_zone"]
        except Exception as e:
            # Gracefully handle when user_data is None, or does not have a "time_zone" entry
            time_zone = None
        return time_zone

    def get_language_code(self):
        try:
            lang = self.user_data["language_code"]
        except Exception as e:
            # Gracefully handle when user_data is None, or does not have a "language_code" entry
            lang = None
        return lang

    def has_permission(self, domain, permission, data=None):
        if self.role_id is None:
            return False
        else:
            role = UserRole.get(self.role_id)
            if role is not None:
                return role.permissions.has(permission, data)
            else:
                return False
    
    def get_role(self, domain=None):
        """
        Get the role object for this user
        """
        if domain is None:
            # default to current_domain for django templates
            domain = self.current_domain
        
        if domain != self.domain:
            return None
        elif self.role_id is None:
            return None
        else:
            return UserRole.get(self.role_id)
    
    def set_role(self, domain, role_qualified_id):
        """
        role_qualified_id is either 'none' 'admin' 'user-role:[id]'
        """
        if domain != self.domain:
            raise Exception("Mobile worker does not have access to domain %s" % domain)
        else:
            # For now, only allow mobile workers to take non-admin roles
            if role_qualified_id.startswith('user-role:'):
                self.role_id = role_qualified_id[len('user-role:'):]
            elif role_qualified_id == 'none':
                self.role_id = None
            else:
                raise Exception("unexpected role_qualified_id: %r" % role_qualified_id)

class WebUser(CouchUser, AuthorizableMixin):
    betahack = BooleanProperty(default=False)
    teams = StringListProperty()

    #do sync and create still work?

    def sync_from_old_couch_user(self, old_couch_user):
        super(WebUser, self).sync_from_old_couch_user(old_couch_user)
        for dm in old_couch_user.web_account.domain_memberships:
            dm.domain = normalize_domain_name(dm.domain)
            self.domain_memberships.append(dm)
            self.domains.append(dm.domain)

    def is_global_admin(self):
        # override this function to pass global admin rights off to django
        return self.is_superuser

    @classmethod
    def create(cls, domain, username, password, email=None, uuid='', date='', **kwargs):
        web_user = super(WebUser, cls).create(domain, username, password, email, uuid, date, **kwargs)
        if domain:
            web_user.add_domain_membership(domain, **kwargs)
        web_user.save()
        return web_user

    def is_commcare_user(self):
        return False

    def is_web_user(self):
        return True

    def get_email(self):
        return self.email or self.username

    @property
    def projects(self):
        return map(Domain.get_by_name, self.domains)

    def get_domains(self):
        from corehq.apps.orgs.models import Team
        domains = [dm.domain for dm in self.domain_memberships]
        if self.teams:
            for team_name, team_id in self.teams:
                team = Team.get(team_id)
                team_domains = [dm.domain for dm in team.domain_memberships]
                for domain in team_domains:
                    if domain not in domains:
                        domains.append(domain)
        return domains

    def has_permission(self, domain, permission, data=None):
        # is_admin is the same as having all the permissions set
        from corehq.apps.orgs.models import Team
        if self.is_global_admin():
            return True
        elif self.is_domain_admin(domain):
            return True

        dm_list = list()

        dm = self.get_domain_membership(domain)
        if dm:
            dm_list.append([dm, ''])

        for team_name, team_id in self.teams:
            team = Team.get(team_id)
            if team.get_domain_membership(domain) and team.get_domain_membership(domain).role:
                dm_list.append([team.get_domain_membership(domain), '(' + team_name + ')'])

        #now find out which dm has the highest permissions
        if dm_list:
            role = self.total_domain_membership(dm_list, domain)
            dm = CustomDomainMembership(domain=domain, custom_role=role)
            return dm.has_permission(permission, data)
        else:
            return False



    def get_role(self, domain=None):
        """
        Get the role object for this user

        """
        from corehq.apps.orgs.models import Team
        if domain is None:
            # default to current_domain for django templates
            domain = self.current_domain

        if self.is_global_admin():
            return AdminUserRole(domain=domain)

        dm_list = list()

        dm = self.get_domain_membership(domain)
        if dm:
            dm_list.append([dm, ''])

        for team_name, team_id in self.teams:
            team = Team.get(team_id)
            if team.get_domain_membership(domain) and team.get_domain_membership(domain).role:
                dm_list.append([team.get_domain_membership(domain), ' (' + team_name + ')'])

        #now find out which dm has the highest permissions
        if dm_list:
            return self.total_domain_membership(dm_list, domain)
        else:
            raise DomainMembershipError()



    def total_domain_membership(self, domain_memberships, domain):
        #sort out the permissions
        total_permission = Permissions()
        total_reports_list = list()
        if domain_memberships:
            for domain_membership, membership_source in domain_memberships:
                permission = domain_membership.permissions
                total_permission |= permission

            #set up a user role
            return UserRole(domain=domain, permissions=total_permission, name=', '.join(["%s %s" % (domain_membership.role.name, membership_source) for domain_membership, membership_source in domain_memberships]))
            #set up a domain_membership


class FakeUser(WebUser):
    """
    Prevent actually saving user types that don't exist in the database
    """
    def save(self, **kwargs):
        raise NotImplementedError("You aren't allowed to do that!")
        
    
class PublicUser(FakeUser):
    """
    Public users have read-only access to certain domains
    """

    domain_memberships = None

    def __init__(self, domain, **kwargs):
        super(PublicUser, self).__init__(**kwargs)
        self.domain = domain
        self.domains = [domain]
        dm = CustomDomainMembership(domain=domain, is_admin=False)
        dm.set_permission('view_reports', True)
        self.domain_memberships = [dm]

    def get_role(self, domain=None):
        assert(domain == self.domain)
        return super(PublicUser, self).get_role(domain)

class InvalidUser(FakeUser):
    """
    Public users have read-only access to certain domains
    """
    
    def is_member_of(self, domain_qs):
        return False
    
#
# Django  models go here
#
class Invitation(Document):
    """
    When we invite someone to a domain it gets stored here.
    """
    domain = StringProperty()
    email = StringProperty()
#    is_domain_admin = BooleanProperty()
    invited_by = StringProperty()
    invited_on = DateTimeProperty()
    is_accepted = BooleanProperty(default=False)

    role = StringProperty()

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

class RemoveWebUserRecord(DeleteRecord):
    user_id = StringProperty()
    domain_membership = SchemaProperty(DomainMembership)

    def undo(self):
        user = WebUser.get_by_user_id(self.user_id)
        user.add_domain_membership(**self.domain_membership._doc)
        user.save()

from .signals import *
from corehq.apps.domain.models import Domain
