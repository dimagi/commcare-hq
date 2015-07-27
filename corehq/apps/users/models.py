"""
couch models go here
"""
from __future__ import absolute_import
import copy
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re

from restkit.errors import NoMoreData
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils.translation import ugettext as _
from corehq.apps.commtrack.dbaccessors import get_supply_point_case_by_location
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain_by_owner
from corehq.apps.sofabed.models import CaseData
from dimagi.ext.couchdbkit import *
from couchdbkit.resource import ResourceNotFound
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.database import get_safe_write_kwargs, iter_docs
from dimagi.utils.logging import notify_exception

from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.make_uuid import random_hex
from dimagi.utils.modules import to_function
from corehq.util.quickcache import skippable_quickcache
from casexml.apps.case.xml import V2
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from casexml.apps.phone.models import User as CaseXMLUser
from corehq.apps.cachehq.mixins import CachedCouchDocumentMixin
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.domain.utils import normalize_domain_name, domain_restricts_superusers
from corehq.apps.domain.models import LicenseAgreement
from corehq.apps.users.util import (
    normalize_username,
    user_data_from_registration_form,
    user_display_string,
)
from corehq.apps.users.tasks import tag_docs_as_deleted, tag_forms_as_deleted_rebuild_associated_cases
from corehq.apps.users.exceptions import InvalidLocationConfig
from corehq.apps.sms.mixin import (
    CommCareMobileContactMixin,
    InvalidFormatException,
    PhoneNumberInUseException,
    VerifiedNumber,
)
from couchforms.models import XFormInstance
from dimagi.utils.couch.undo import DeleteRecord, DELETED_SUFFIX
from corehq.apps.hqwebapp.tasks import send_html_email_async
from dimagi.utils.mixins import UnicodeMixIn
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.django.database import get_unique_value
from dimagi.utils.parsing import json_format_datetime
from xml.etree import ElementTree

from couchdbkit.exceptions import ResourceConflict, NoResultFound

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

    @classmethod
    def wrap(cls, data):
        # this is why you don't store module paths in the database...
        MOVED_REPORT_MAPPING = {
            'corehq.apps.reports.standard.inspect.CaseListReport': 'corehq.apps.reports.standard.cases.basic.CaseListReport'
        }
        reports = data.get('view_report_list', [])
        for i, report_name in enumerate(reports):
            if report_name in MOVED_REPORT_MAPPING:
                reports[i] = MOVED_REPORT_MAPPING[report_name]

        return super(Permissions, cls).wrap(data)

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
        for name, value in permissions.properties().items():
            if isinstance(value, (BooleanProperty, ListProperty)):
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


class UserRolePresets(object):
    READ_ONLY_NO_REPORTS = "Read Only (No Reports)"
    APP_EDITOR = "App Editor"
    READ_ONLY = "Read Only"
    FIELD_IMPLEMENTER = "Field Implementer"
    INITIAL_ROLES = (
        READ_ONLY,
        APP_EDITOR,
        FIELD_IMPLEMENTER,
    )

    @classmethod
    def get_preset_map(cls):
        return {
            cls.READ_ONLY_NO_REPORTS: lambda: Permissions(),
            cls.READ_ONLY: lambda: Permissions(view_reports=True),
            cls.FIELD_IMPLEMENTER: lambda: Permissions(edit_commcare_users=True, view_reports=True),
            cls.APP_EDITOR: lambda: Permissions(edit_apps=True, view_reports=True),
        }

    @classmethod
    def get_permissions(cls, preset):
        preset_map = cls.get_preset_map()
        if preset not in preset_map.keys():
            return None
        return preset_map[preset]()


class UserRole(Document):
    domain = StringProperty()
    name = StringProperty()
    permissions = SchemaProperty(Permissions)
    is_archived = BooleanProperty(default=False)

    def get_qualified_id(self):
        return 'user-role:%s' % self.get_id

    @classmethod
    def by_domain(cls, domain, is_archived=False):
        # todo change this view to show is_archived status or move to PRBAC UserRole
        all_roles = cls.view(
            'users/roles_by_domain',
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
            reduce=False,
        )
        return filter(lambda x: x.is_archived == is_archived, all_roles)

    @classmethod
    def by_domain_and_name(cls, domain, name, is_archived=False):
        # todo change this view to show is_archived status or move to PRBAC UserRole
        all_roles = cls.view(
            'users/roles_by_domain',
            key=[domain, name],
            include_docs=True,
            reduce=False,
        )
        return filter(lambda x: x.is_archived == is_archived, all_roles)

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
            preset_match = filter(
                lambda x: x[1]() == permissions,
                UserRolePresets.get_preset_map().items()
            )
            if preset_match:
                return preset_match[0][0]
        role = cls(domain=domain, permissions=permissions, name=get_name())
        role.save()
        return role

    @classmethod
    def get_read_only_role_by_domain(cls, domain):
        try:
            return cls.by_domain_and_name(domain, UserRolePresets.READ_ONLY)[0]
        except (IndexError, TypeError):
            return cls.get_or_create_with_permissions(
                domain, UserRolePresets.get_permissions(
                    UserRolePresets.READ_ONLY), UserRolePresets.READ_ONLY)

    @classmethod
    def get_custom_roles_by_domain(cls, domain):
        return filter(
            lambda x: x.name not in UserRolePresets.INITIAL_ROLES,
            cls.by_domain(domain)
        )

    @classmethod
    def reset_initial_roles_for_domain(cls, domain):
        initial_roles = filter(
            lambda x: x.name in UserRolePresets.INITIAL_ROLES,
            cls.by_domain(domain)
        )
        for role in initial_roles:
            role.permissions = UserRolePresets.get_permissions(role.name)
            role.save()

    @classmethod
    def archive_custom_roles_for_domain(cls, domain):
        custom_roles = cls.get_custom_roles_by_domain(domain)
        for role in custom_roles:
            role.is_archived = True
            role.save()

    @classmethod
    def unarchive_roles_for_domain(cls, domain):
        archived_roles = cls.by_domain(domain, is_archived=True)
        for role in archived_roles:
            role.is_archived = False
            role.save()

    @classmethod
    def init_domain_with_presets(cls, domain):
        for role_name in UserRolePresets.INITIAL_ROLES:
            cls.get_or_create_with_permissions(
                domain, UserRolePresets.get_permissions(role_name), role_name)

    @classmethod
    def get_default(cls, domain=None):
        return cls(permissions=Permissions(), domain=domain, name=None)

    @classmethod
    def role_choices(cls, domain):
        return [(role.get_qualified_id(), role.name or '(No Name)') for role in [AdminUserRole(domain=domain)] + list(cls.by_domain(domain))]

    @classmethod
    def commcareuser_role_choices(cls, domain):
        return [('none','(none)')] + [(role.get_qualified_id(), role.name or '(No Name)') for role in list(cls.by_domain(domain))]

    @property
    def ids_of_assigned_users(self):
        from corehq.apps.api.es import UserES
        query = {"query": {"bool": {"must": [{"term": {"user.doc_type": "WebUser"}},
                                             {"term": {"user.domain_memberships.role_id": self.get_id}},
                                             {"term": {"user.domain_memberships.domain": self.domain}},
                                             {"term": {"user.is_active": True}},
                                             {"term": {"user.base_doc": "couchuser"}}],
                                    }}, "fields": []}
        query_results = UserES(self.domain).run_query(es_query=query, security_check=False)
        assigned_user_ids = []
        for user in query_results['hits'].get('hits', []):
            assigned_user_ids.append(user['_id'])

        return assigned_user_ids

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

class Membership(DocumentSchema):
#   If we find a need for making UserRoles more general and decoupling it from domain then most of the role stuff from
#   Domain membership can be put in here
    is_admin = BooleanProperty(default=False)

class DomainMembership(Membership):
    """
    Each user can have multiple accounts on the
    web domain. This is primarily for Dimagi staff.
    """

    domain = StringProperty()
    timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    override_global_tz = BooleanProperty(default=False)
    role_id = StringProperty()
    location_id = StringProperty()
    program_id = StringProperty()

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
            try:
                return UserRole.get(self.role_id)
            except ResourceNotFound:
                logging.exception('no role with id %s found in domain %s' % (self.role_id, self.domain))
                return None
        else:
            return None

    def has_permission(self, permission, data=None):
        return self.is_admin or self.permissions.has(permission, data)

    def viewable_reports(self):
        return self.permissions.view_report_list

    class Meta:
        app_label = 'users'

class OrgMembership(Membership):
    organization = StringProperty()
    team_ids = StringListProperty(default=[]) # a set of ids corresponding to which teams the user is a member of

class OrgMembershipError(Exception):
    pass

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


class IsMemberOfMixin(DocumentSchema):

    def _is_member_of(self, domain):
        return domain in self.get_domains() or (
            self.is_global_admin() and
            not domain_restricts_superusers(domain)
        )

    def is_member_of(self, domain_qs):
        """
        takes either a domain name or a domain object and returns whether the user is part of that domain
        either natively or through a team
        """

        try:
            domain = domain_qs.name
        except Exception:
            domain = domain_qs
        return self._is_member_of(domain)


    def is_global_admin(self):
        # subclasses to override if they want this functionality
        return False

class _AuthorizableMixin(IsMemberOfMixin):
    """
        Use either SingleMembershipMixin or MultiMembershipMixin instead of this
    """
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

    def add_domain_membership(self, domain, timezone=None, **kwargs):
        for d in self.domain_memberships:
            if d.domain == domain:
                if domain not in self.domains:
                    raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
                return

        domain_obj = Domain.get_by_name(domain, strict=True)
        if not domain_obj:
            domain_obj = Domain(is_active=True, name=domain, date_created=datetime.utcnow())
            domain_obj.save()

        if timezone:
            domain_membership = DomainMembership(domain=domain, timezone=timezone, **kwargs)
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
                    record = DomainRemovalRecord(
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

    def transfer_domain_membership(self, domain, to_user, create_record=False, is_admin=True):
        to_user.add_domain_membership(domain, is_admin=is_admin)
        self.delete_domain_membership(domain, create_record=create_record)

    @memoized
    def is_domain_admin(self, domain=None):
        if not domain:
            # hack for template
            if hasattr(self, 'current_domain'):
                # this is a hack needed because we can't pass parameters from views
                domain = self.current_domain
            else:
                return False # no domain, no admin
        if self.is_global_admin() and (domain is None or not domain_restricts_superusers(domain)):
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

    @memoized
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

    @memoized
    def get_role(self, domain=None, checking_global_admin=True):
        """
        Get the role object for this user

        """
        if domain is None:
            # default to current_domain for django templates
            if hasattr(self, 'current_domain'):
                domain = self.current_domain
            else:
                domain = None

        if checking_global_admin and self.is_global_admin():
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
        elif role_qualified_id == 'none':
            dm.role_id = None
        else:
            raise Exception("unexpected role_qualified_id is %r" % role_qualified_id)

        self.has_permission.reset_cache(self)
        self.get_role.reset_cache(self)

    def role_label(self, domain=None):
        if not domain:
            try:
                domain = self.current_domain
            except (AttributeError, KeyError):
                return None
        try:
            return self.get_role(domain, checking_global_admin=False).name
        except TypeError:
            return "Unknown User"
        except DomainMembershipError:
            return "Unauthorized User"
        except Exception:
            return None

class SingleMembershipMixin(_AuthorizableMixin):
    domain_membership = SchemaProperty(DomainMembership)

    @property
    def domains(self):
        return [self.domain]

    @property
    def domain_memberships(self):
        return [self.domain_membership]

    def add_domain_membership(self, domain, timezone=None, **kwargs):
        raise NotImplementedError

    def delete_domain_membership(self, domain, create_record=False):
        raise NotImplementedError

    def transfer_domain_membership(self, domain, user, create_record=False):
        raise NotImplementedError

class MultiMembershipMixin(_AuthorizableMixin):
    domains = StringListProperty()
    domain_memberships = SchemaListProperty(DomainMembership)

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


class EulaMixin(DocumentSchema):
    CURRENT_VERSION = '2.0' # Set this to the most up to date version of the eula
    eulas = SchemaListProperty(LicenseAgreement)

    @classmethod
    def migrate_eula(cls, data):
        if 'eula' in data:
            data['eulas'] = [data['eula']]
            data['eulas'][0]['version'] = '1.0'
            del data['eula']
        return data

    def is_eula_signed(self, version=CURRENT_VERSION):
        if self.is_superuser:
            return True
        for eula in self.eulas:
            if eula.version == version:
                return eula.signed
        return False

    def get_eula(self, version):
        for eula in self.eulas:
            if eula.version == version:
                return eula
        return None

    @property
    def eula(self, version=CURRENT_VERSION):
        current_eula = self.get_eula(version)
        if not current_eula:
            current_eula = LicenseAgreement(type="End User License Agreement", version=version)
            self.eulas.append(current_eula)
        assert current_eula.type == "End User License Agreement"
        return current_eula


class KeyboardShortcutsConfig(DocumentSchema):
    enabled = BooleanProperty(False)
    main_key = StringProperty(choices=["ctrl", "option", "command", "alt", "shift", "control"])
    main_keycode = IntegerProperty()


class CouchUser(Document, DjangoUserMixin, IsMemberOfMixin, UnicodeMixIn, EulaMixin):
    """
    A user (for web and commcare)
    """
    base_doc = 'CouchUser'
    device_ids = ListProperty()
    phone_numbers = ListProperty()
    created_on = DateTimeProperty(default=datetime(year=1900, month=1, day=1))
    #    For now, 'status' is things like:
    #        ('auto_created',     'Automatically created from form submission.'),
    #        ('phone_registered', 'Registered from phone'),
    #        ('site_edited',     'Manually added or edited from the HQ website.'),
    status = StringProperty()
    language = StringProperty()
    email_opt_out = BooleanProperty(default=False)
    subscribed_to_commcare_users = BooleanProperty(default=False)
    announcements_seen = ListProperty()
    keyboard_shortcuts = SchemaProperty(KeyboardShortcutsConfig)
    user_data = DictProperty()
    location_id = StringProperty()
    has_built_app = BooleanProperty(default=False)

    _user = None
    _user_checked = False

    @classmethod
    def wrap(cls, data, should_save=False):
        if data.has_key("organizations"):
            del data["organizations"]
            should_save = True

        data = cls.migrate_eula(data)

        couch_user = super(CouchUser, cls).wrap(data)
        if should_save:
            couch_user.save()
        return couch_user

    @classmethod
    def es_fakes(cls, domain, fields=None, start_at=None, size=None, wrap=True):
        """
        Get users from ES.  Use instead of by_domain()
        This is faster than big db calls, but only returns partial data.
        Set wrap to False to get a raw dict object (much faster).
        This raw dict can be passed to _report_user_dict.
        The save method has been disabled.
        """
        fields = fields or ['_id', 'username', 'first_name', 'last_name',
                'doc_type', 'is_active', 'email']
        raw = es_wrapper('users', domain=domain, doc_type=cls.__name__,
                fields=fields, start_at=start_at, size=size)
        if not wrap:
            return raw
        def save(*args, **kwargs):
            raise NotImplementedError("This is a fake user, don't save it!")
        ESUser = type(cls.__name__, (cls,), {'save': save})
        return [ESUser(u) for u in raw]

    class AccountTypeError(Exception):
        pass

    class Inconsistent(Exception):
        pass

    class InvalidID(Exception):
        pass

    @property
    def is_dimagi(self):
        return self.username.endswith('@dimagi.com')

    @property
    def raw_username(self):
        if self.doc_type == "CommCareUser":
            return self.username.split("@")[0]
        else:
            return self.username

    def html_username(self):
        username = self.raw_username
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

    def __unicode__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.get_id)

    def get_email(self):
        return self.email

    def is_commcare_user(self):
        return self._get_user_type() == 'commcare'

    def is_web_user(self):
        return self._get_user_type() == 'web'

    def _get_user_type(self):
        if self.doc_type == 'WebUser':
            return 'web'
        elif self.doc_type == 'CommCareUser':
            return 'commcare'
        else:
            raise NotImplementedError()

    @property
    def projects(self):
        return map(Domain.get_by_name, self.get_domains())

    @property
    def full_name(self):
        return (u"%s %s" % (self.first_name or u'', self.last_name or u'')).strip()

    @property
    def human_friendly_name(self):
        return self.full_name if self.full_name else self.username

    @property
    def name_in_filters(self):
        username = self.username.split("@")[0]
        return "%s <%s>" % (self.full_name, username) if self.full_name else username

    formatted_name = full_name
    name = full_name

    def set_full_name(self, full_name):
        data = full_name.split()
        self.first_name = data.pop(0)
        self.last_name = ' '.join(data)

    @property
    def user_session_data(self):
        from corehq.apps.custom_data_fields.models import SYSTEM_PREFIX

        session_data = copy.copy(self.user_data)
        session_data.update({
            '{}_first_name'.format(SYSTEM_PREFIX): self.first_name,
            '{}_last_name'.format(SYSTEM_PREFIX): self.last_name,
            '{}_phone_number'.format(SYSTEM_PREFIX): self.phone_number,
        })
        return session_data

    def delete(self):
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
        super(CouchUser, self).delete() # Call the "real" delete() method.
        couch_user_post_save.send_robust(sender='couch_user', couch_user=self)

    def delete_phone_number(self, phone_number):
        for i in range(0,len(self.phone_numbers)):
            if self.phone_numbers[i] == phone_number:
                del self.phone_numbers[i]
                break
        self.save()
        self.delete_verified_number(phone_number)

    def get_django_user(self):
        return User.objects.get(username__iexact=self.username)

    def add_phone_number(self, phone_number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(phone_number, basestring):
            phone_number = str(phone_number)
        self.phone_numbers = _add_to_list(self.phone_numbers, phone_number, default)

    def set_default_phone_number(self, phone_number):
        self.add_phone_number(phone_number, True)
        self.save()

    @property
    def default_phone_number(self):
        return _get_default(self.phone_numbers)
    phone_number = default_phone_number

    def phone_numbers_extended(self, active_user=None):
        # TODO: what about web users... do we not want to verify phone numbers
        # for them too? if so, CommCareMobileContactMixin should be on CouchUser,
        # not CommCareUser

        # hack to work around the above issue
        if not isinstance(self, CommCareMobileContactMixin):
            return [{'number': phone, 'status': 'unverified', 'contact': None} for phone in self.phone_numbers]

        verified = self.get_verified_numbers(True)
        def extend_phone(phone):
            extended_info = {}
            contact = verified.get(phone)
            if contact:
                status = 'verified' if contact.verified else 'pending'
            else:
                try:
                    self.verify_unique_number(phone)
                    status = 'unverified'
                except PhoneNumberInUseException:
                    status = 'duplicate'

                    duplicate = VerifiedNumber.by_phone(phone, include_pending=True)
                    assert duplicate is not None, 'expected duplicate VerifiedNumber entry'

                    # TODO seems like this could be a useful utility function? where to put it...
                    try:
                        doc_type = {
                            'CouchUser': 'user',
                            'CommCareUser': 'user',
                            'CommCareCase': 'case',
                            'CommConnectCase': 'case',
                        }[duplicate.owner_doc_type]
                        from corehq.apps.users.views.mobile import EditCommCareUserView
                        url_ref, doc_id_param = {
                            'user': (EditCommCareUserView.urlname, 'couch_user_id'),
                            'case': ('case_details', 'case_id'),
                        }[doc_type]
                        dup_url = reverse(url_ref, kwargs={'domain': duplicate.domain, doc_id_param: duplicate.owner_id})

                        if active_user is None or active_user.is_member_of(duplicate.domain):
                            extended_info['dup_url'] = dup_url
                    except Exception, e:
                        pass
                except InvalidFormatException:
                    status = 'invalid'
            extended_info.update({'number': phone, 'status': status, 'contact': contact})
            return extended_info
        return [extend_phone(phone) for phone in self.phone_numbers]


    @property
    def couch_id(self):
        return self._id

    # Couch view wrappers
    @classmethod
    def all(cls):
        return CouchUser.view("users/by_username", include_docs=True, reduce=False)

    @classmethod
    def by_domain(cls, domain, is_active=True, reduce=False, limit=None, skip=0, strict=False, doc_type=None):
        flag = "active" if is_active else "inactive"
        doc_type = doc_type or cls.__name__
        if cls.__name__ == "CouchUser":
            key = [flag, domain]
        else:
            key = [flag, domain, doc_type]
        extra_args = dict()
        if not reduce:
            extra_args.update(include_docs=True)
            if limit is not None:
                extra_args.update(
                    limit=limit,
                    skip=skip
                )

        return cls.view("users/by_domain",
            reduce=reduce,
            startkey=key,
            endkey=key + [{}],
            #stale=None if strict else settings.COUCH_STALE_QUERY,
            **extra_args
        ).all()


    @classmethod
    def ids_by_domain(cls, domain, is_active=True):
        flag = "active" if is_active else "inactive"
        if cls.__name__ == "CouchUser":
            key = [flag, domain]
        else:
            key = [flag, domain, cls.__name__]
        return [r['id'] for r in cls.get_db().view("users/by_domain",
            startkey=key,
            endkey=key + [{}],
            reduce=False,
            include_docs=False,
        )]

    @classmethod
    def total_by_domain(cls, domain, is_active=True):
        data = cls.by_domain(domain, is_active, reduce=True)
        return data[0].get('value', 0) if data else 0

    @classmethod
    def phone_users_by_domain(cls, domain):
        return CouchUser.view("users/phone_users_by_domain",
            startkey=[domain],
            endkey=[domain, {}],
            include_docs=True,
        )

    def is_previewer(self):
        from django.conf import settings
        return (self.is_superuser or
                re.compile(settings.PREVIEWER_RE).match(self.username))

    def sync_from_django_user(self, django_user):
        if not django_user:
            django_user = self.get_django_user()
        for attr in DjangoUserMixin.ATTRS:
            # name might be truncated so don't backwards sync
            one_way_attrs = ['first_name', 'last_name']
            if attr not in one_way_attrs or not getattr(self, attr):
                # don't sync one-way attrs back to couch unless we didn't have
                # something there in the first place. this is hack to allow
                # unit test workflows that create the django user first to work
                setattr(self, attr, getattr(django_user, attr))

    def sync_to_django_user(self):
        try:
            django_user = self.get_django_user()
        except User.DoesNotExist:
            django_user = User(username=self.username)
        for attr in DjangoUserMixin.ATTRS:
            attr_val = getattr(self, attr) or ''
            # truncate names when saving to django
            if attr == 'first_name' or attr == 'last_name':
                attr_val = attr_val[:30]
            setattr(django_user, attr, attr_val)
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
        if source['doc_type'] == 'CouchUser' and \
                source.has_key('commcare_accounts') and \
                source.has_key('web_accounts'):
            from . import old_couch_user_models
            # todo: remove this functionality and the old user models module
            logging.error('still accessing old user models')
            user_id = old_couch_user_models.CouchUser.wrap(source).default_account.login_id
            return cls.get_by_user_id(user_id)
        else:
            return {
                'WebUser': WebUser,
                'CommCareUser': CommCareUser,
                'FakeUser': FakeUser,
            }[source['doc_type']].wrap(source)

    @classmethod
    @skippable_quickcache(['username'], skip_arg='strict')
    def get_by_username(cls, username, strict=True):
        def get(stale, raise_if_none):
            result = cls.get_db().view('users/by_username',
                key=username,
                include_docs=True,
                reduce=False,
                stale=stale if not strict else None,
            )
            return result.one(except_all=raise_if_none)
        try:
            result = get(stale=settings.COUCH_STALE_QUERY, raise_if_none=True)
            if result['doc'] is None or result['doc']['username'] != username:
                raise NoResultFound
        except NoMoreData:
            logging.exception('called get_by_username(%r) and it failed pretty bad' % username)
            raise
        except NoResultFound:
            result = get(stale=None, raise_if_none=False)

        if result:
            return cls.wrap_correctly(result['doc'])
        else:
            return None

    def clear_quickcache_for_user(self):
        self.get_by_username.clear(self.__class__, self.username)
        Domain.active_for_couch_user.clear(self)

    @classmethod
    def get_by_default_phone(cls, phone_number):
        result = cls.get_db().view('users/by_default_phone', key=phone_number, include_docs=True).one()
        if result:
            return cls.wrap_correctly(result['doc'])
        else:
            return None

    @classmethod
    def get_by_user_id(cls, userID, domain=None):
        """
        if domain is given, checks to make sure the user is a member of that domain
        returns None if there's no user found or if the domain check fails
        """
        try:
            couch_user = cls.wrap_correctly(cache_core.cached_open_doc(cls.get_db(), userID))
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
    def create(cls, domain, username, password, email=None, uuid='', date='',
               first_name='', last_name='', **kwargs):
        try:
            django_user = User.objects.get(username=username)
        except User.DoesNotExist:
            django_user = create_user(
                username, password=password, email=email,
                first_name=first_name, last_name=last_name, **kwargs
            )

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

    def to_be_deleted(self):
        return self.base_doc.endswith(DELETED_SUFFIX)

    def change_username(self, username):
        if username == self.username:
            return

        if User.objects.filter(username=username).exists():
            raise self.Inconsistent("User with username %s already exists" % username)

        django_user = self.get_django_user()
        django_user.DO_NOT_SAVE_COUCH_USER = True
        django_user.username = username
        django_user.save()
        self.username = username
        self.save()

    def save(self, **params):
        self.clear_quickcache_for_user()
        # test no username conflict
        by_username = self.get_db().view('users/by_username', key=self.username, reduce=False).first()
        if by_username and by_username['id'] != self._id:
            raise self.Inconsistent("CouchUser with username %s already exists" % self.username)

        if not self.to_be_deleted():
            django_user = self.sync_to_django_user()
            django_user.save()

        super(CouchUser, self).save(**params)

        results = couch_user_post_save.send_robust(sender='couch_user', couch_user=self)
        for result in results:
            # Second argument is None if there was no error
            if result[1]:
                notify_exception(
                    None,
                    message="Error occured while syncing user %s: %s" %
                            (self.username, str(result[1]))
                )



    @classmethod
    def django_user_post_save_signal(cls, sender, django_user, created, max_tries=3):
        if hasattr(django_user, 'DO_NOT_SAVE_COUCH_USER'):
            del django_user.DO_NOT_SAVE_COUCH_USER
        else:
            couch_user = cls.from_django_user(django_user)
            if couch_user:
                couch_user.sync_from_django_user(django_user)

                try:
                    # avoid triggering cyclical sync
                    super(CouchUser, couch_user).save(**get_safe_write_kwargs())
                except ResourceConflict:
                    cls.django_user_post_save_signal(sender, django_user, created, max_tries - 1)

    def is_deleted(self):
        return self.base_doc.endswith(DELETED_SUFFIX)

    def get_viewable_reports(self, domain=None, name=False, slug=False):
        try:
            domain = domain or self.current_domain
        except AttributeError:
            domain = None

        if self.is_commcare_user():
            role = self.get_role(domain)
            if role is None:
                models = []
            else:
                models = role.permissions.view_report_list
        else:
            dm = self.get_domain_membership(domain)
            models = dm.viewable_reports() if dm else []

        def slug_name(model):
            try:
                if slug:
                    return to_function(model).slug
                if name:
                    return to_function(model).name
            except AttributeError:
                logging.warning("Unable to load report model: %s", model)
                return None

        if slug or name:
            return filter(None, [slug_name(m) for m in models])

        return models

    def get_exportable_reports(self, domain=None):
        viewable_reports = self.get_viewable_reports(domain=domain, slug=True)
        from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher
        export_reports = set(DataInterfaceDispatcher().get_reports_dict(domain).keys())
        return list(export_reports.intersection(viewable_reports))

    def can_export_data(self, domain=None):
        can_see_exports = self.can_view_reports()
        if not can_see_exports:
            can_see_exports = bool(self.get_exportable_reports(domain))
        return can_see_exports

    def is_current_web_user(self, request):
        return self.user_id == request.couch_user.user_id

    # gets hit for can_view_reports, etc.
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
        raise AttributeError("'{}' object has no attribute '{}'".format(
            self.__class__.__name__, item))


class CommCareUser(CouchUser, SingleMembershipMixin, CommCareMobileContactMixin):

    domain = StringProperty()
    registering_device_id = StringProperty()
    # used by loadtesting framework - should typically be empty
    loadtest_factor = IntegerProperty()

    @classmethod
    def wrap(cls, data):
        # migrations from using role_id to using the domain_memberships
        role_id = None
        should_save = False
        if not data.has_key('domain_membership') or not data['domain_membership'].get('domain', None):
            should_save = True
        if data.has_key('role_id'):
            role_id = data["role_id"]
            del data['role_id']
            should_save = True
        self = super(CommCareUser, cls).wrap(data)
        if should_save:
            self.domain_membership = DomainMembership(domain=data.get('domain', ""))
            if role_id:
                self.domain_membership.role_id = role_id

        return self

    def save(self, **params):
        super(CommCareUser, self).save(**params)

        from corehq.apps.users.signals import commcare_user_post_save
        results = commcare_user_post_save.send_robust(sender='couch_user', couch_user=self)
        for result in results:
            # Second argument is None if there was no error
            if result[1]:
                notify_exception(
                    None,
                    message="Error occured while syncing user %s: %s" %
                            (self.username, str(result[1]))
                )

    @property
    @memoized
    def project(self):
        return Domain.get_by_name(self.domain)

    def is_domain_admin(self, domain=None):
        # cloudcare workaround
        return False

    def sync_from_old_couch_user(self, old_couch_user):
        super(CommCareUser, self).sync_from_old_couch_user(old_couch_user)
        self.domain                 = normalize_domain_name(old_couch_user.default_account.domain)
        self.registering_device_id  = old_couch_user.default_account.registering_device_id
        self.user_data              = old_couch_user.default_account.user_data

    @classmethod
    def create(cls, domain, username, password, email=None, uuid='', date='', phone_number=None, commit=True,
               **kwargs):
        """
        used to be a function called `create_hq_user_from_commcare_registration_info`

        """
        commcare_user = super(CommCareUser, cls).create(domain, username, password, email, uuid, date, **kwargs)
        if phone_number is not None:
            commcare_user.add_phone_number(phone_number)

        device_id = kwargs.get('device_id', '')
        user_data = kwargs.get('user_data', {})
        # populate the couch user
        commcare_user.domain = domain
        commcare_user.device_ids = [device_id]
        commcare_user.registering_device_id = device_id
        commcare_user.user_data = user_data

        commcare_user.domain_membership = DomainMembership(domain=domain, **kwargs)

        if commit:
            commcare_user.save(**get_safe_write_kwargs())

        return commcare_user

    @property
    def filter_flag(self):
        from corehq.apps.reports.models import HQUserType
        return HQUserType.REGISTERED

    @property
    def project(self):
        return Domain.get_by_name(self.domain)

    @property
    def username_in_report(self):
        return user_display_string(self.username, self.first_name, self.last_name)

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

    def is_commcare_user(self):
        return True

    def is_web_user(self):
        return False

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
        user = CaseXMLUser(
            user_id=self.userID,
            username=self.raw_username,
            password=self.password,
            date_joined=self.date_joined,
            user_data=self.user_data,
            domain=self.domain,
            loadtest_factor=self.loadtest_factor,
            first_name=self.first_name,
            last_name=self.last_name,
            phone_number=self.phone_number,
        )

        def get_owner_ids():
            return self.get_owner_ids()
        user.get_owner_ids = get_owner_ids
        user._hq_user = self # don't tell anyone that we snuck this here
        return user

    def get_forms(self, deleted=False, wrap=True, include_docs=False):
        if deleted:
            view_name = 'users/deleted_forms_by_user'
            startkey = [self.user_id]
        else:
            view_name = 'reports_forms/all_forms'
            startkey = ['submission user', self.domain, self.user_id]

        db = XFormInstance.get_db()
        doc_ids = [r['id'] for r in db.view(view_name,
            startkey=startkey,
            endkey=startkey + [{}],
            reduce=False,
            include_docs=False,
        )]
        if wrap or include_docs:
            for doc in iter_docs(db, doc_ids):
                yield XFormInstance.wrap(doc) if wrap else doc
        else:
            for id in doc_ids:
                yield id

    @property
    def form_count(self):
        key = ["submission user", self.domain, self.user_id]
        result = XFormInstance.view('reports_forms/all_forms',
            startkey=key,
            endkey=key + [{}],
            reduce=True
        ).one()
        if result:
            return result['value']
        else:
            return 0

    def _get_deleted_cases(self):
        case_ids = [r["id"] for r in CommCareCase.get_db().view(
            'users/deleted_cases_by_user',
            startkey=[self.user_id],
            endkey=[self.user_id, {}],
            reduce=False,
        )]
        for doc in iter_docs(CommCareCase.get_db(), case_ids):
            yield CommCareCase.wrap(doc)

    def _get_case_docs(self):
        case_ids = get_case_ids_in_domain_by_owner(
            self.domain, owner_id=self.user_id)
        return iter_docs(CommCareCase.get_db(), case_ids)

    @property
    def analytics_only_case_count(self):
        """
        Get an approximate count of cases which were last submitted to by this user.

        This number is not guaranteed to be 100% accurate since it depends on a secondary index (sofabed)
        """
        return CaseData.objects.filter(user_id=self._id).count()

    def location_group_ids(self):
        """
        Return generated ID's that represent the virtual
        groups used to send location data in the restore
        payload.
        """
        def get_sharing_id(loc):
            return loc.case_sharing_group_object(self._id)._id

        if self.sql_location.location_type.view_descendants:
            locs = (self.sql_location.get_descendants(include_self=True)
                                     .filter(location_type__shares_cases=True))
            return map(get_sharing_id, locs)
        elif self.sql_location.location_type.shares_cases:
            return [get_sharing_id(self.sql_location)]
        else:
            return []

    def get_owner_ids(self):
        from corehq.apps.groups.models import Group

        owner_ids = [self.user_id]
        owner_ids.extend(Group.by_user(self, wrap=False))

        if self.project.uses_locations and self.location:
            owner_ids.extend(self.location_group_ids())
        return owner_ids

    def retire(self):
        suffix = DELETED_SUFFIX
        deletion_id = random_hex()
        deleted_cases = set()
        # doc_type remains the same, since the views use base_doc instead
        if not self.base_doc.endswith(suffix):
            self.base_doc += suffix
            self['-deletion_id'] = deletion_id

        for caselist in chunked(self._get_case_docs(), 50):
            tag_docs_as_deleted.delay(CommCareCase, caselist, deletion_id)
            for case in caselist:
                deleted_cases.add(case['_id'])

        for formlist in chunked(self.get_forms(wrap=False, include_docs=True), 50):
            tag_forms_as_deleted_rebuild_associated_cases.delay(formlist, deletion_id, deleted_cases=deleted_cases)

        for phone_number in self.get_verified_numbers(True).values():
            phone_number.retire(deletion_id)

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
        for case in self._get_deleted_cases():
            case.doc_type = chop_suffix(case.doc_type)
            case.save()
        self.save()

    def get_case_sharing_groups(self):
        from corehq.apps.groups.models import Group
        # get faked location group object
        groups = []
        if self.location and self.location.location_type_object.shares_cases:
            if self.location.location_type_object.view_descendants:
                for loc in self.sql_location.get_descendants():
                    groups.append(loc.case_sharing_group_object(
                        self._id,
                    ))

            groups.append(self.sql_location.case_sharing_group_object(self._id))

        groups += [group for group in Group.by_user(self) if group.case_sharing]

        return groups

    @classmethod
    def cannot_share(cls, domain, limit=None, skip=0):
        users_checked = list(cls.by_domain(domain, limit=limit, skip=skip))
        if not users_checked:
            # stop fetching when you come back with none
            return []
        users = [user for user in users_checked if len(user.get_case_sharing_groups()) != 1]
        if limit is not None:
            total = cls.total_by_domain(domain)
            max_limit = min(total - skip, limit)
            if len(users) < max_limit:
                new_limit = max_limit - len(users_checked)
                new_skip = skip + len(users_checked)
                users.extend(cls.cannot_share(domain, new_limit, new_skip))
                return users
        return users

    def get_group_ids(self):
        from corehq.apps.groups.models import Group
        return Group.by_user(self, wrap=False)

    def set_groups(self, group_ids):
        from corehq.apps.groups.models import Group
        desired = set(group_ids)
        current = set(self.get_group_ids())
        touched = []
        for to_add in desired - current:
            group = Group.get(to_add)
            group.add_user(self._id, save=False)
            touched.append(group)
        for to_remove in current - desired:
            group = Group.get(to_remove)
            group.remove_user(self._id, save=False)
            touched.append(group)

        Group.bulk_save(touched)


    def get_time_zone(self):
        try:
            time_zone = self.user_data["time_zone"]
        except Exception as e:
            # Gracefully handle when user_data is None, or does not have a "time_zone" entry
            time_zone = None
        return time_zone

    def get_language_code(self):
        if self.user_data and "language_code" in self.user_data:
            # Old way
            return self.user_data["language_code"]
        else:
            return self.language

    @property
    @memoized
    def location(self):
        from corehq.apps.locations.models import Location
        if self.location_id:
            return Location.get(self.location_id)
        else:
            return None

    @property
    def sql_location(self):
        from corehq.apps.locations.models import SQLLocation
        if self.location_id:
            return SQLLocation.objects.get(location_id=self.location_id)
        else:
            return None

    def set_location(self, location):
        """
        Set the location, and all important user data, for
        the user.
        """
        from corehq.apps.commtrack.models import SupplyPointCase
        from corehq.apps.fixtures.models import UserFixtureType

        self.user_data['commcare_location_id'] = location._id

        if not location.location_type_object.administrative:
            # just need to trigger a get or create to make sure
            # this exists, otherwise things blow up
            SupplyPointCase.get_or_create_by_location(location)

            self.user_data.update({
                'commtrack-supply-point': location.sql_location.supply_point_id
            })

        if self.project.supports_multiple_locations_per_user:
            # TODO is it possible to only remove this
            # access if it was not previously granted by
            # the bulk upload?

            # we only add the new one because we don't know
            # if we can actually remove the old..
            self.add_location_delegate(location)
        else:
            self.create_location_delegates([location])

        self.user_data.update({
            'commcare_primary_case_sharing_id':
            location._id
        })

        self.location_id = location._id
        self.update_fixture_status(UserFixtureType.LOCATION)
        self.save()

    def unset_location(self):
        """
        Unset the location and remove all associated user data and cases
        """
        from corehq.apps.fixtures.models import UserFixtureType

        self.user_data.pop('commcare_location_id', None)
        self.user_data.pop('commtrack-supply-point', None)
        self.user_data.pop('commcare_primary_case_sharing_id', None)
        self.location_id = None
        self.clear_location_delegates()
        self.update_fixture_status(UserFixtureType.LOCATION)
        self.save()

    @property
    def _locations(self):
        """
        Hidden access to a users delgate location list.

        Should be removed (and this code moved back under
        self.location) sometime after migration and things
        are settled.
        """
        from corehq.apps.locations.models import Location
        from corehq.apps.commtrack.models import SupplyPointCase

        def _get_linked_supply_point_ids():
            mapping = self.get_location_map_case()
            if mapping:
                return [index.referenced_id for index in mapping.indices]
            return []

        def _get_linked_supply_points():
            for doc in iter_docs(
                CommCareCase.get_db(),
                _get_linked_supply_point_ids()
            ):
                yield SupplyPointCase.wrap(doc)

        def _gen():
            location_ids = [sp.location_id for sp in _get_linked_supply_points()]
            for doc in iter_docs(Location.get_db(), location_ids):
                yield Location.wrap(doc)

        return list(_gen())

    @property
    def locations(self):
        """
        This method is only used for domains with the multiple
        locations per user flag set. It will error if you try
        to call it on a normal domain.
        """
        if not self.project.supports_multiple_locations_per_user:
            raise InvalidLocationConfig(
                "Attempting to access multiple locations for a user in a domain that does not support this."
            )

        return self._locations

    def supply_point_index_mapping(self, supply_point, clear=False):
        from corehq.apps.commtrack.exceptions import (
            LinkedSupplyPointNotFoundError
        )

        if supply_point:
            return {
                'supply_point-' + supply_point._id:
                (
                    supply_point.type,
                    supply_point._id if not clear else ''
                )
            }
        else:
            raise LinkedSupplyPointNotFoundError(
                "There was no linked supply point for the location."
            )

    def add_location_delegate(self, location):
        """
        Add a single location to the delgate case access.

        This will dynamically create a supply point if the supply point isn't found.
        """
        # todo: the dynamic supply point creation is bad and should be removed.
        from corehq.apps.commtrack.models import SupplyPointCase

        sp = SupplyPointCase.get_or_create_by_location(location)

        if not location.location_type_object.administrative:
            from corehq.apps.commtrack.util import submit_mapping_case_block
            submit_mapping_case_block(self, self.supply_point_index_mapping(sp))

    def submit_location_block(self, caseblock):
        from corehq.apps.hqcase.utils import submit_case_blocks

        submit_case_blocks(
            ElementTree.tostring(
                caseblock.as_xml(format_datetime=json_format_datetime)
            ),
            self.domain,
            self.username,
            self._id
        )

    def remove_location_delegate(self, location):
        """
        Remove a single location from the case delagate access.
        """

        sp = get_supply_point_case_by_location(location)

        mapping = self.get_location_map_case()

        if not location.location_type_object.administrative:
            if mapping and location._id in [loc._id for loc in self.locations]:
                caseblock = CaseBlock(
                    create=False,
                    case_id=mapping._id,
                    version=V2,
                    index=self.supply_point_index_mapping(sp, True)
                )

                self.submit_location_block(caseblock)

    def clear_location_delegates(self):
        """
        Wipe all case delagate access.
        """
        from casexml.apps.case.cleanup import safe_hard_delete
        mapping = self.get_location_map_case()
        if mapping:
            safe_hard_delete(mapping)

    def create_location_delegates(self, locations):
        """
        Submit the case blocks creating the delgate case access
        for the location(s).
        """
        from corehq.apps.commtrack.models import SupplyPointCase

        if self.project.supports_multiple_locations_per_user:
            new_locs_set = set([loc._id for loc in locations])
            old_locs_set = set([loc._id for loc in self.locations])

            if new_locs_set == old_locs_set:
                # don't do anything if the list passed is the same
                # as the users current locations. the check is a little messy
                # as we can't compare the location objects themself
                return

        self.clear_location_delegates()

        if not locations:
            return

        index = {}
        for location in locations:
            if not location.location_type_object.administrative:
                sp = get_supply_point_case_by_location(location)
                index.update(self.supply_point_index_mapping(sp))

        from corehq.apps.commtrack.util import location_map_case_id
        caseblock = CaseBlock(
            create=True,
            case_type=USER_LOCATION_OWNER_MAP_TYPE,
            case_id=location_map_case_id(self),
            version=V2,
            owner_id=self._id,
            index=index
        )

        self.submit_location_block(caseblock)

    def get_location_map_case(self):
        """
        Returns the location mapping case for this supply point.

        That lets us give access to the supply point via
        delagate access.
        """
        try:
            from corehq.apps.commtrack.util import location_map_case_id
            return CommCareCase.get(location_map_case_id(self))
        except ResourceNotFound:
            return None

    @property
    @skippable_quickcache(['self._id'], lambda _: settings.UNIT_TESTING)
    def fixture_statuses(self):
        """Returns all of the last modified times for each fixture type"""
        return self.get_fixture_statuses()

    def get_fixture_statuses(self):
        from corehq.apps.fixtures.models import UserFixtureType, UserFixtureStatus
        last_modifieds = {choice[0]: UserFixtureStatus.DEFAULT_LAST_MODIFIED
                          for choice in UserFixtureType.CHOICES}
        for fixture_status in UserFixtureStatus.objects.filter(user_id=self._id):
            last_modifieds[fixture_status.fixture_type] = fixture_status.last_modified
        return last_modifieds

    def fixture_status(self, fixture_type):
        try:
            return self.fixture_statuses[fixture_type]
        except KeyError:
            from corehq.apps.fixtures.models import UserFixtureStatus
            return UserFixtureStatus.DEFAULT_LAST_MODIFIED

    def update_fixture_status(self, fixture_type):
        from corehq.apps.fixtures.models import UserFixtureStatus
        now = datetime.utcnow()
        user_fixture_sync, new = UserFixtureStatus.objects.get_or_create(
            user_id=self._id,
            fixture_type=fixture_type,
            defaults={'last_modified': now},
        )
        if not new:
            user_fixture_sync.last_modified = now
            user_fixture_sync.save()

    def __repr__(self):
        return ("{class_name}(username={self.username!r})".format(
            class_name=self.__class__.__name__,
            self=self
        ))


class OrgMembershipMixin(DocumentSchema):
    org_memberships = SchemaListProperty(OrgMembership)

    @property
    def organizations(self):
        return [om.organization for om in self.org_memberships]

    def get_organizations(self):
        from corehq.apps.orgs.models import Organization
        return filter(None, [Organization.get_by_name(org) for org in self.organizations])

    def is_member_of_org(self, org_name_or_model):
        """
        takes either a organization name or an organization object and returns whether the user is part of that org
        """
        try:
            org = org_name_or_model.name
        except Exception:
            org = org_name_or_model
        return org in self.organizations

    def get_org_membership(self, org):
        for om in self.org_memberships:
            if om.organization == org:
                return om
        return None

    def add_org_membership(self, org, **kwargs):
        from corehq.apps.orgs.models import Organization
        if self.get_org_membership(org):
            return

        organization = Organization.get_by_name(org, strict=True)
        if not organization:
            raise OrgMembershipError("Cannot add org membership -- Organization %s does not exist" % org)

        kwargs.pop("organization", None) # prevents next line from raising an error due to two organization values being given to OrgMembership
        self.org_memberships.append(OrgMembership(organization=org, **kwargs))

    def delete_org_membership(self, org, create_record=False):
        record = None
        for i, om in enumerate(self.org_memberships):
            if om.organization == org:
                if create_record:
                    record = OrgRemovalRecord(org_membership = om, user_id=self.user_id)
                del self.org_memberships[i]
                break
        if create_record:
            if record:
                record.save()
                return record
            else:
                raise OrgMembershipError("Cannot delete org membership -- Organization %s does not exist" % org)

    def is_org_admin(self, org):
        om = self.get_org_membership(org)
        return om and om.is_admin

    def is_member_of_team(self, org, team_id):
        om = self.get_org_membership(org)
        return om and team_id in om.team_ids

    def add_to_team(self, org, team_id):
        om = self.get_org_membership(org)
        if not om:
            raise OrgMembershipError("Cannot add team -- %s is not a member of the %s organization" %
                                     (self.username, org))

        from corehq.apps.orgs.models import Team
        team = Team.get(team_id)
        if not team or team.organization != org:
            raise OrgMembershipError("Cannot add team -- Team(%s) does not exist in organization %s" % (team_id, org))

        om.team_ids.append(team_id)

    def remove_from_team(self, org, team_id):
        om = self.get_org_membership(org)
        if om:
            om.team_ids.remove(team_id)

    def set_org_admin(self, org):
        om = self.get_org_membership(org)
        if not om:
            raise OrgMembershipError("Cannot set admin -- %s is not a member of the %s organization" %
                                     (self.username, org))
        om.is_admin = True


class WebUser(CouchUser, MultiMembershipMixin, OrgMembershipMixin, CommCareMobileContactMixin):
    #do sync and create still work?

    program_id = StringProperty()

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
    def by_organization(cls, org, team_id=None):
        key = [org] if team_id is None else [org, team_id]
        users = cls.view("users/by_org_and_team",
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
        ).all()
        # return a list of users with the duplicates removed
        return dict([(u.get_id, u) for u in users]).values()

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

    def get_time_zone(self):
        from corehq.util.timezones.utils import get_timezone_for_user

        if hasattr(self, 'current_domain'):
            domain = self.current_domain
        elif len(self.domains) > 0:
            domain = self.domains[0]
        else:
            return None

        timezone = get_timezone_for_user(self.user_id, domain)
        return timezone.zone

    def get_language_code(self):
        return self.language

    def get_teams(self, ids_only=False):
        from corehq.apps.orgs.models import Team
        teams = []

        def get_valid_teams(team_ids):
            team_db = Team.get_db()
            for t_id in team_ids:
                if team_db.doc_exist(t_id):
                    yield Team.get(t_id)
                else:
                    logging.info("Note: team %s does not exist for %s" % (t_id, self))

        for om in self.org_memberships:
            if not ids_only:
                teams.extend(list(get_valid_teams(om.team_ids)))
            else:
                teams.extend(om.team_ids)
        return teams

    def get_domains(self):
        domains = [dm.domain for dm in self.domain_memberships]
        for team in self.get_teams():
            team_domains = [dm.domain for dm in team.domain_memberships]
            for domain in team_domains:
                if domain not in domains:
                    domains.append(domain)
        return domains

    @memoized
    def has_permission(self, domain, permission, data=None):
        # is_admin is the same as having all the permissions set
        if (self.is_global_admin() and (domain is None or not domain_restricts_superusers(domain))):
            return True
        elif self.is_domain_admin(domain):
            return True

        dm_list = list()

        dm = self.get_domain_membership(domain)
        if dm:
            dm_list.append([dm, ''])

        for team in self.get_teams():
            if team.get_domain_membership(domain) and team.get_domain_membership(domain).role:
                dm_list.append([team.get_domain_membership(domain), '(' + team.name + ')'])

        #now find out which dm has the highest permissions
        if dm_list:
            role = self.total_domain_membership(dm_list, domain)
            dm = CustomDomainMembership(domain=domain, custom_role=role)
            return dm.has_permission(permission, data)
        else:
            return False

    @memoized
    def get_role(self, domain=None, include_teams=True, checking_global_admin=True):
        """
        Get the role object for this user

        """
        if domain is None:
            # default to current_domain for django templates
            domain = self.current_domain

        if checking_global_admin and self.is_global_admin():
            return AdminUserRole(domain=domain)

        if not include_teams:
            return super(WebUser, self).get_role(domain)

        dm_list = list()

        dm = self.get_domain_membership(domain)
        if dm:
            dm_list.append([dm, ''])

        for team in self.get_teams():
            if team.get_domain_membership(domain) and team.get_domain_membership(domain).role:
                dm_list.append([team.get_domain_membership(domain), ' (' + team.name + ')'])

        #now find out which dm has the highest permissions
        if dm_list:
            return self.total_domain_membership(dm_list, domain)
        else:
            raise DomainMembershipError()

    def total_domain_membership(self, domain_memberships, domain):
        #sort out the permissions
        total_permission = Permissions()
        if domain_memberships:
            for domain_membership, membership_source in domain_memberships:
                permission = domain_membership.permissions
                total_permission |= permission

            #set up a user role
            return UserRole(domain=domain, permissions=total_permission,
                            name=', '.join(["%s %s" % (dm.role.name, ms) for dm, ms in domain_memberships if dm.role]))
            #set up a domain_membership

    @classmethod
    def get_admins_by_domain(cls, domain):
        user_ids = cls.ids_by_domain(domain)
        for user_doc in iter_docs(cls.get_db(), user_ids):
            web_user = cls.wrap(user_doc)
            if web_user.is_domain_admin(domain):
                yield web_user

    @classmethod
    def get_dimagi_emails_by_domain(cls, domain):
        user_ids = cls.ids_by_domain(domain)
        for user_doc in iter_docs(cls.get_db(), user_ids):
            if user_doc['email'].endswith('@dimagi.com'):
                yield user_doc['email']

    def get_location_id(self, domain):
        return getattr(self.get_domain_membership(domain), 'location_id', None)

    @memoized
    def get_sql_location(self, domain):
        from corehq.apps.locations.models import SQLLocation
        loc_id = self.get_location_id(domain)
        return SQLLocation.objects.get(location_id=loc_id) if loc_id else None

    @memoized
    def get_location(self, domain):
        from corehq.apps.locations.models import Location
        loc_id = self.get_location_id(domain)
        return Location.get(loc_id) if loc_id else None


class FakeUser(WebUser):
    """
    Prevent actually saving user types that don't exist in the database
    """
    def save(self, **kwargs):
        raise NotImplementedError("You aren't allowed to do that!")

    @property
    def _id(self):
        return "fake-user"


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

    @memoized
    def get_role(self, domain=None, checking_global_admin=None):
        assert(domain == self.domain)
        return super(PublicUser, self).get_role(domain)

    def is_eula_signed(self):
        return True # hack for public domain so eula modal doesn't keep popping up

    def get_domains(self):
        return []

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
    email = StringProperty()
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
        raise NotImplementedError

    @property
    def is_expired(self):
        return False


class DomainInvitation(CachedCouchDocumentMixin, Invitation):
    """
    When we invite someone to a domain it gets stored here.
    """
    domain = StringProperty()
    role = StringProperty()
    doc_type = "Invitation"

    def send_activation_email(self, remaining_days=30):
        url = absolute_reverse("domain_accept_invitation",
                               args=[self.domain, self.get_id])
        params = {"domain": self.domain, "url": url, 'days': remaining_days,
                  "inviter": self.get_inviter().formatted_name}
        text_content = render_to_string("domain/email/domain_invite.txt", params)
        html_content = render_to_string("domain/email/domain_invite.html", params)
        subject = _('Invitation from %s to join CommCareHQ') % self.get_inviter().formatted_name
        send_html_email_async.delay(subject, self.email, html_content,
                                    text_content=text_content,
                                    cc=[self.get_inviter().get_email()],
                                    email_from=settings.DEFAULT_FROM_EMAIL)

    @classmethod
    def by_domain(cls, domain, is_active=True):
        key = [domain]

        return cls.view("users/open_invitations_by_domain",
            reduce=False,
            startkey=key,
            endkey=key + [{}],
            include_docs=True,
        ).all()

    @classmethod
    def by_email(cls, email, is_active=True):
        return cls.view("users/open_invitations_by_email",
                        reduce=False,
                        key=[email],
                        include_docs=True,
                        stale=settings.COUCH_STALE_QUERY,
                        ).all()

    @property
    def is_expired(self):
        return self.invited_on.date() + relativedelta(months=1) < datetime.utcnow().date()


class DomainRemovalRecord(DeleteRecord):
    user_id = StringProperty()
    domain_membership = SchemaProperty(DomainMembership)

    def undo(self):
        user = WebUser.get_by_user_id(self.user_id)
        user.add_domain_membership(**self.domain_membership._doc)
        user.save()

class OrgRemovalRecord(DeleteRecord):
    user_id = StringProperty()
    org_membership = SchemaProperty(OrgMembership)

    def undo(self):
        user = WebUser.get_by_user_id(self.user_id)
        some_args = self.org_membership._doc
        user.add_org_membership(some_args["organization"], **some_args)
        user.save()

class UserCache(object):
    def __init__(self):
        self.cache = {}

    def get(self, user_id):
        if not user_id:
            return None
        if user_id in self.cache:
            return self.cache[user_id]
        else:
            user = CouchUser.get_by_user_id(user_id)
            self.cache[user_id] = user
            return user


from .signals import *
from corehq.apps.domain.models import Domain
