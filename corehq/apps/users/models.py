import hmac
import json
import logging
import re
from collections import namedtuple
from datetime import datetime, date
from hashlib import sha1
from typing import List
from uuid import uuid4
from xml.etree import cElementTree as ElementTree

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, models, router
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import override as override_language
from django.utils.translation import gettext as _

from couchdbkit import MultipleResultsFound, ResourceNotFound
from couchdbkit.exceptions import BadValueError, ResourceConflict
from dateutil.relativedelta import relativedelta
from memoized import memoized

from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.models import OTARestoreCommCareUser, OTARestoreWebUser
from casexml.apps.phone.restore_caching import get_loadtest_factor_for_restore_cache_key
from corehq.form_processor.models import XFormInstance
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DateProperty,
    DateTimeProperty,
    DictProperty,
    Document,
    DocumentSchema,
    IntegerProperty,
    ListProperty,
    SchemaListProperty,
    SchemaProperty,
    StringListProperty,
    StringProperty,
)
from dimagi.utils.chunked import chunked
from dimagi.utils.couch import CriticalSection
from dimagi.utils.couch.database import get_safe_write_kwargs, iter_docs
from dimagi.utils.couch.undo import DELETED_SUFFIX, DeleteRecord
from dimagi.utils.dates import (
    force_to_datetime,
    get_date_from_month_and_year_string,
)
from dimagi.utils.logging import log_signal_errors, notify_exception
from dimagi.utils.modules import to_function
from dimagi.utils.web import get_static_url_prefix

from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.domain.models import Domain, LicenseAgreement
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.domain.utils import (
    domain_restricts_superusers,
    guess_domain_language,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sms.mixin import CommCareMobileContactMixin, apply_leniency
from corehq.apps.user_importer.models import UserUploadRecord
from corehq.apps.users.exceptions import IllegalAccountConfirmation
from corehq.apps.users.permissions import EXPORT_PERMISSIONS
from corehq.apps.users.tasks import (
    tag_cases_as_deleted_and_remove_indices,
    tag_forms_as_deleted_rebuild_associated_cases,
    tag_system_forms_as_deleted,
    undelete_system_forms,
)
from corehq.apps.users.util import (
    filter_by_app,
    log_user_change,
    user_display_string,
    user_location_data,
    username_to_user_id,
    bulk_auto_deactivate_commcare_users,
    is_dimagi_email,
)
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.form_processor.models import CommCareCase
from corehq.toggles import TABLEAU_USER_SYNCING
from corehq.util.dates import get_timestamp
from corehq.util.models import BouncedEmail
from corehq.util.quickcache import quickcache
from corehq.util.view_utils import absolute_reverse

from .models_role import (  # noqa
    RoleAssignableBy,
    RolePermission,
    Permission,
    StaticRole,
    UserRole,
)
from .user_data import SQLUserData  # noqa
from corehq import toggles, privileges
from corehq.apps.accounting.utils import domain_has_privilege

WEB_USER = 'web'
COMMCARE_USER = 'commcare'

MAX_WEB_USER_LOGIN_ATTEMPTS = 5
MAX_COMMCARE_USER_LOGIN_ATTEMPTS = 500

EULA_CURRENT_VERSION = '3.0'  # Set this to the most up to date version of the eula


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


class PermissionInfo(namedtuple("Permission", "name, allow")):
    """Data class that represents a single permission.
    Some permissions can be parameterized to restrict access to only specific items
    instead of ALL items.
    """
    ALLOW_ALL = "*"

    def __new__(cls, name, allow=ALLOW_ALL):
        allow = allow if allow == cls.ALLOW_ALL else tuple(allow)
        if allow != cls.ALLOW_ALL and name not in PARAMETERIZED_PERMISSIONS:
            raise TypeError(f"Permission '{name}' does not support parameterization")
        return super(PermissionInfo, cls).__new__(cls, name, allow)

    @property
    def allow_all(self):
        return self.allow == self.ALLOW_ALL

    @property
    def allowed_items(self):
        if self.allow_all:
            return []
        assert isinstance(self.allow, tuple), self.allow
        return self.allow


PARAMETERIZED_PERMISSIONS = {
    'manage_data_registry': 'manage_data_registry_list',
    'view_data_registry_contents': 'view_data_registry_contents_list',
    'view_reports': 'view_report_list',
    'view_tableau': 'view_tableau_list',
}


class HqPermissions(DocumentSchema):
    edit_web_users = BooleanProperty(default=False)
    view_web_users = BooleanProperty(default=False)

    # only domain admins can edit roles, due to security issues.
    view_roles = BooleanProperty(default=False)

    edit_commcare_users = BooleanProperty(default=False)
    view_commcare_users = BooleanProperty(default=False)

    edit_groups = BooleanProperty(default=False)
    view_groups = BooleanProperty(default=False)
    edit_users_in_groups = BooleanProperty(default=False)

    edit_locations = BooleanProperty(default=False)
    view_locations = BooleanProperty(default=False)
    edit_users_in_locations = BooleanProperty(default=False)

    view_data_dict = BooleanProperty(default=False)
    edit_data_dict = BooleanProperty(default=False)

    edit_motech = BooleanProperty(default=False)
    edit_data = BooleanProperty(default=False)
    edit_apps = BooleanProperty(default=False)
    view_apps = BooleanProperty(default=False)
    edit_shared_exports = BooleanProperty(default=False)
    access_all_locations = BooleanProperty(default=True)
    access_api = BooleanProperty(default=False)
    access_web_apps = BooleanProperty(default=False)
    edit_messaging = BooleanProperty(default=False)
    access_release_management = BooleanProperty(default=False)
    edit_linked_configurations = BooleanProperty(default=False)

    edit_reports = BooleanProperty(default=False)
    download_reports = BooleanProperty(default=False)
    view_reports = BooleanProperty(default=False)
    view_report_list = StringListProperty(default=[])
    edit_ucrs = BooleanProperty(default=False)
    view_tableau = BooleanProperty(default=False)
    view_tableau_list = StringListProperty(default=[])

    edit_billing = BooleanProperty(default=False)
    report_an_issue = BooleanProperty(default=True)

    access_mobile_endpoints = BooleanProperty(default=False)

    view_file_dropzone = BooleanProperty(default=False)
    edit_file_dropzone = BooleanProperty(default=False)

    login_as_all_users = BooleanProperty(default=False)
    limited_login_as = BooleanProperty(default=False)
    access_default_login_as_user = BooleanProperty(default=False)

    manage_data_registry = BooleanProperty(default=False)
    manage_data_registry_list = StringListProperty(default=[])
    view_data_registry_contents = BooleanProperty(default=False)
    view_data_registry_contents_list = StringListProperty(default=[])
    manage_attendance_tracking = BooleanProperty(default=False)

    manage_domain_alerts = BooleanProperty(default=False)

    @classmethod
    def from_permission_list(cls, permission_list):
        """Converts a list of Permission objects into a Permissions object"""
        permissions = HqPermissions.min()
        for perm in permission_list:
            setattr(permissions, perm.name, perm.allow_all)
            if perm.name in PARAMETERIZED_PERMISSIONS:
                setattr(permissions, PARAMETERIZED_PERMISSIONS[perm.name], list(perm.allowed_items))
        return permissions

    def normalize(self, previous=None):
        if not self.access_all_locations:
            # The following permissions cannot be granted to location-restricted
            # roles.
            self.edit_web_users = False
            self.view_web_users = False
            self.edit_groups = False
            self.view_groups = False
            self.edit_apps = False
            self.view_roles = False
            self.edit_reports = False
            self.edit_billing = False
            self.edit_data_dict = False
            self.view_data_dict = False

        if self.edit_web_users:
            self.view_web_users = True

        if self.edit_commcare_users:
            self.view_commcare_users = True

        if self.edit_groups:
            self.view_groups = True
        else:
            self.edit_users_in_groups = False

        if self.edit_locations:
            self.view_locations = True
        else:
            self.edit_users_in_locations = False

        if self.edit_data_dict:
            self.view_data_dict = True

        if self.edit_apps:
            self.view_apps = True

        if not (self.view_reports or self.view_report_list):
            self.download_reports = False

        if self.access_release_management and previous:
            # Do not overwrite edit_linked_configurations, so that if access_release_management
            # is removed, the previous value for edit_linked_configurations can be restored
            self.edit_linked_configurations = previous.edit_linked_configurations

    @classmethod
    @memoized
    def permission_names(cls):
        """Returns a list of permission names"""
        return {
            name for name, value in HqPermissions.properties().items()
            if isinstance(value, BooleanProperty)
        }

    @classmethod
    def diff(cls, left, right):
        left_dict = {info.name: info.allow for info in left.to_list()}
        right_dict = {info.name: info.allow for info in right.to_list()}

        all_names = set(left_dict.keys()) | right_dict.keys()

        diffs = []

        for name in all_names:
            if (name not in left_dict
                    or name not in right_dict
                    or left_dict[name] != right_dict[name]):
                diffs.append(name)

        return diffs

    def to_list(self) -> List[PermissionInfo]:
        """Returns a list of Permission objects for those permissions that are enabled."""
        return list(self._yield_enabled())

    def _yield_enabled(self):
        for name in HqPermissions.permission_names():
            value = getattr(self, name)
            list_value = None
            if name in PARAMETERIZED_PERMISSIONS:
                list_name = PARAMETERIZED_PERMISSIONS[name]
                list_value = getattr(self, list_name)
            if value or list_value:
                yield PermissionInfo(name, allow=PermissionInfo.ALLOW_ALL if value else list_value)

    def view_report(self, report):
        return self.view_reports or report in self.view_report_list

    def view_tableau_viz(self, viz_id):
        if not self.access_all_locations:
            return False
        return self.view_tableau or viz_id in self.view_tableau_list

    def has(self, permission, data=None):
        if data:
            return getattr(self, permission)(data)
        else:
            return getattr(self, permission)

    def _getattr(self, name):
        a = getattr(self, name)
        if isinstance(a, list):
            a = set(a)
        return a

    def __eq__(self, other):
        for name in self.properties():
            if self._getattr(name) != other._getattr(name):
                return False
        return True

    @classmethod
    def max(cls):
        return HqPermissions._all(True)

    @classmethod
    def min(cls):
        return HqPermissions._all(False)

    @classmethod
    def _all(cls, value: bool):
        perms = HqPermissions()
        for name in HqPermissions.permission_names():
            setattr(perms, name, value)
        return perms


class DomainMembershipError(Exception):
    pass


class Membership(DocumentSchema):
    # If we find a need for making UserRoles more general and decoupling it from a domain
    # then most of the role stuff from Domain membership can be put in here
    is_admin = BooleanProperty(default=False)


class DomainMembership(Membership):
    """
    Each user can have multiple accounts on individual domains
    """
    _user_type = None

    domain = StringProperty()
    timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    override_global_tz = BooleanProperty(default=False)
    role_id = StringProperty()
    # This should not be set directly but using set_location method only
    location_id = StringProperty()
    assigned_location_ids = StringListProperty()
    program_id = StringProperty()
    last_accessed = DateProperty()

    @property
    def permissions(self):
        if self.role:
            return self.role.permissions
        else:
            return HqPermissions()

    @classmethod
    def wrap(cls, data):
        if data.get('subject'):
            data['domain'] = data['subject']
            del data['subject']

        return super(DomainMembership, cls).wrap(data)

    @property
    @memoized
    def role(self):
        if self.is_admin:
            return StaticRole.domain_admin(self.domain)
        elif self.role_id:
            try:
                return UserRole.objects.by_couch_id(self.role_id)
            except UserRole.DoesNotExist:
                logging.exception('no role found in domain', extra={
                    'role_id': self.role_id,
                    'domain': self.domain
                })
                return None
        else:
            return self.get_default_role()

    def get_default_role(self):
        if self._user_type == COMMCARE_USER:
            return UserRole.commcare_user_default(self.domain)
        return None

    def has_permission(self, permission, data=None):
        return self.is_admin or self.permissions.has(permission, data)

    def viewable_reports(self):
        return self.permissions.view_report_list

    class Meta(object):
        app_label = 'users'


class IsMemberOfMixin(DocumentSchema):

    def _is_member_of(self, domain, allow_enterprise):
        if not domain:
            return False

        if self.is_global_admin() and not domain_restricts_superusers(domain):
            return True

        domains = self.get_domains()
        if domain in domains:
            return True

        if allow_enterprise:
            from corehq.apps.enterprise.models import EnterprisePermissions
            config = EnterprisePermissions.get_by_domain(domain)
            if config.is_enabled and domain in config.domains:
                return self.is_member_of(config.source_domain, allow_enterprise=False)

        return False

    def is_member_of(self, domain_qs, allow_enterprise=False):
        """
        Takes either a domain name or a domain object and returns whether the user is part of that domain
        """

        try:
            domain = domain_qs.name
        except Exception:
            domain = domain_qs
        return self._is_member_of(domain, allow_enterprise)

    def is_global_admin(self):
        # subclasses to override if they want this functionality
        return False


class _AuthorizableMixin(IsMemberOfMixin):
    """
        Use either SingleMembershipMixin or MultiMembershipMixin instead of this
    """

    def get_domain_membership(self, domain, allow_enterprise=True):
        domain_membership = None
        try:
            for d in self.domain_memberships:
                if d.domain == domain:
                    domain_membership = d
                    if domain not in self.domains:
                        raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
            if not domain_membership:
                if domain in self.domains:
                    raise self.Inconsistent("Domain '%s' is in domain but not in domain_memberships" % domain)
                from corehq.apps.enterprise.models import EnterprisePermissions
                config = EnterprisePermissions.get_by_domain(domain)
                if allow_enterprise and config.is_enabled and domain in config.domains:
                    return self.get_domain_membership(config.source_domain, allow_enterprise=False)
        except self.Inconsistent as e:
            logging.warning(e)
            self.domains = [d.domain for d in self.domain_memberships]

        if domain_membership:
            # set user type on membership to support default roles for 'commcare' users
            domain_membership._user_type = self._get_user_type()
        return domain_membership

    def add_domain_membership(self, domain, timezone=None, **kwargs):
        for d in self.domain_memberships:
            if d.domain == domain:
                if domain not in self.domains:
                    raise self.Inconsistent("Domain '%s' is in domain_memberships but not domains" % domain)
                return

        domain_obj = Domain.get_by_name(domain, strict=True)

        if timezone:
            domain_membership = DomainMembership(domain=domain, timezone=timezone, **kwargs)
        else:
            domain_membership = DomainMembership(domain=domain,
                                            timezone=domain_obj.default_timezone,
                                            **kwargs)
        self.domain_memberships.append(domain_membership)
        self.domains.append(domain)

    def add_as_web_user(self, domain, role, location_id=None, program_id=None):
        domain_obj = Domain.get_by_name(domain)
        self.add_domain_membership(domain=domain)
        self.set_role(domain, role)
        if domain_obj.commtrack_enabled:
            self.get_domain_membership(domain).program_id = program_id
        if domain_obj.uses_locations and location_id:
            self.set_location(domain, location_id)
        self.save()

    def delete_domain_membership(self, domain, create_record=False):
        """
        If create_record is True, a DomainRemovalRecord is created so that the
        action can be undone, and the DomainRemovalRecord is returned.

        If create_record is True but the domain membership is not found,
        then None is returned.
        """
        self.get_by_user_id.clear(self.__class__, self.user_id, domain)
        record = None

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

        if record:
            record.save()
            return record

    def transfer_domain_membership(self, domain, to_user, create_record=False, is_admin=True):
        to_user.add_domain_membership(domain, is_admin=is_admin)
        self.delete_domain_membership(domain, create_record=create_record)

    @memoized
    def is_domain_admin(self, domain=None):
        # this is a hack needed because we can't pass parameters from views
        domain = domain or getattr(self, 'current_domain', None)
        if not domain:
            return False  # no domain, no admin
        if self.is_global_admin() and not domain_restricts_superusers(domain):
            return True
        dm = self.get_domain_membership(domain, allow_enterprise=True)
        if dm:
            return dm.is_admin
        else:
            return False

    # I'm not sure this is the correct place for this, as it turns a generic module
    #  into one that knows about ERM specifics. It might make more sense to move this into
    #  the domain membership module, as that module knows about specific permissions.
    # However, because this class is the barrier between the user and domain membership,
    # exposing new functionality on domain membership wouldn't change the problem.
    # An alternate solution would be to expose this functionality directly on the WebUser class, instead.
    def can_edit_linked_data(self, domain):
        return (
            self.has_permission(domain, 'access_release_management')
            or self.has_permission(domain, 'edit_linked_configurations')
        )

    def get_domains(self):
        domains = [dm.domain for dm in self.domain_memberships]
        if set(domains) == set(self.domains):
            return domains
        else:
            raise self.Inconsistent("domains and domain_memberships out of sync")

    @memoized
    def has_permission(self, domain, permission, data=None):
        # is_admin is the same as having all the permissions set
        if self.is_global_admin() and (domain is None or not domain_restricts_superusers(domain)):
            return True
        elif self.is_domain_admin(domain):
            return True

        dm = self.get_domain_membership(domain, allow_enterprise=True)
        if dm:
            return dm.has_permission(permission, data)
        return False

    @memoized
    def get_role(self, domain=None, checking_global_admin=True, allow_enterprise=False):
        """
        Get the role object for this user
        """
        # default to current_domain for django templates
        domain = domain or getattr(self, 'current_domain', None)

        if checking_global_admin and self.is_global_admin():
            return StaticRole.domain_admin(domain)
        if self.is_member_of(domain, allow_enterprise):
            dm = self.get_domain_membership(domain, allow_enterprise)
            if dm:
                return dm.role
        raise DomainMembershipError()

    def set_role(self, domain, role_qualified_id):
        """
        role_qualified_id is either 'admin' 'user-role:[id]'
        """
        dm = self.get_domain_membership(domain)
        dm.is_admin = False
        if role_qualified_id == "admin":
            dm.is_admin = True
            dm.role_id = None
        elif role_qualified_id.startswith('user-role:'):
            dm.role_id = role_qualified_id[len('user-role:'):]
        elif role_qualified_id == 'none':
            dm.role_id = None
        else:
            raise Exception("unexpected role_qualified_id is %r" % role_qualified_id)

        self.has_permission.reset_cache(self)
        self.get_role.reset_cache(self)
        try:
            self.is_domain_admin.reset_cache(self)
        except AttributeError:
            pass
        DomainMembership.role.fget.reset_cache(dm)

    def role_label(self, domain=None):
        domain = domain or getattr(self, 'current_domain', None)
        if not domain:
            return None
        try:
            return self.get_role(domain, checking_global_admin=False).name
        except TypeError:
            return _("Unknown User")
        except DomainMembershipError:
            if self.is_global_admin():
                return _("Dimagi User")
            if self.is_member_of(domain, allow_enterprise=True):
                return _("Enterprise User")
            return _("Unauthorized User")
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

    def __init__(self, validators=None, *args, **kwargs):
        if validators is None:
            validators = ()

        def check_lowercase(value):
            if value and any(char.isupper() for char in value):
                raise BadValueError('uppercase characters not allowed')

        validators += (check_lowercase,)
        super(LowercaseStringProperty, self).__init__(validators=validators, *args, **kwargs)


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
    CURRENT_VERSION = EULA_CURRENT_VERSION
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
        current_domain = getattr(self, 'current_domain', None)
        current_eula = self.eula
        if current_eula.version == version:
            if toggles.FORCE_ANNUAL_TOS.enabled(current_domain):
                if not current_eula.date:
                    return False
                elapsed = datetime.now() - current_eula.date
                return current_eula.signed and elapsed.days < 365
            return current_eula.signed
        return False

    def get_eula(self, version):
        current_eula = None
        for eula in self.eulas:
            if eula.version == version:
                if not current_eula or eula.date > current_eula.date:
                    current_eula = eula
        return current_eula

    def get_eulas(self):
        eulas = self.eulas
        eulas_json = []
        for eula in eulas:
            eulas_json.append(eula.to_json())
        return eulas_json

    @property
    def eula(self, version=CURRENT_VERSION):
        current_eula = self.get_eula(version)
        if not current_eula:
            current_eula = LicenseAgreement(type="End User License Agreement", version=version)
            self.eulas.append(current_eula)
        assert current_eula.type == "End User License Agreement"
        return current_eula


class DeviceAppMeta(DocumentSchema):
    """Metadata for an app on a device"""
    app_id = StringProperty()
    build_id = StringProperty()
    build_version = IntegerProperty()
    last_request = DateTimeProperty()
    last_submission = DateTimeProperty()
    last_sync = DateTimeProperty()
    last_heartbeat = DateTimeProperty()
    num_unsent_forms = IntegerProperty()
    num_quarantined_forms = IntegerProperty()

    def _update_latest_request(self):
        dates = [date for date in (self.last_submission, self.last_heartbeat, self.last_sync) if date]
        self.last_request = max(dates) if dates else None

    def merge(self, other):
        # ensure that last_request is updated
        self.last_request is None and self._update_latest_request()
        other.last_request is None and other._update_latest_request()

        if other.last_request <= self.last_request:
            return

        for key, prop in other.properties().items():
            new_val = getattr(other, key)
            if new_val is not None:
                old_val = getattr(self, key)

                prop_is_date = isinstance(prop, DateTimeProperty)
                if prop_is_date and (old_val and new_val <= old_val):
                    continue  # do not overwrite dates with older ones
                setattr(self, key, new_val)

        self._update_latest_request()


class DeviceIdLastUsed(DocumentSchema):
    device_id = StringProperty()
    last_used = DateTimeProperty()
    commcare_version = StringProperty()
    app_meta = SchemaListProperty(DeviceAppMeta)
    fcm_token = StringProperty()
    fcm_token_timestamp = DateTimeProperty()

    def update_meta(self, commcare_version=None, app_meta=None):
        if commcare_version:
            self.commcare_version = commcare_version
        if app_meta:
            self._merge_app_meta(app_meta)

    def _merge_app_meta(self, app_meta):
        current_meta = self.get_meta_for_app(app_meta.app_id)
        if not current_meta:
            app_meta._update_latest_request()
            self.app_meta.append(app_meta)
        else:
            current_meta.merge(app_meta)

    def get_meta_for_app(self, app_id):
        return filter_by_app(self.app_meta, app_id)

    def get_last_used_app_meta(self):
        try:
            return max(self.app_meta, key=lambda a: a.last_request)
        except ValueError:
            pass

    def __eq__(self, other):
        return all(getattr(self, p) == getattr(other, p) for p in self.properties())

    def update_fcm_token(self, fcm_token, fcm_token_timestamp):
        self.fcm_token = fcm_token
        self.fcm_token_timestamp = fcm_token_timestamp


class LastSubmission(DocumentSchema):
    """Metadata for form sumbissions. This data is keyed by app_id"""
    app_id = StringProperty()
    submission_date = DateTimeProperty()
    build_id = StringProperty()
    device_id = StringProperty()
    build_version = IntegerProperty()
    commcare_version = StringProperty()


class LastSync(DocumentSchema):
    """Metadata for syncs and restores. This data is keyed by app_id"""
    app_id = StringProperty()
    sync_date = DateTimeProperty()
    build_version = IntegerProperty()


class LastBuild(DocumentSchema):
    """
    Build info for the app on the user's phone
    when they last synced or submitted or sent heartbeat request
    """
    app_id = StringProperty()
    build_profile_id = StringProperty()
    build_version = IntegerProperty()
    build_version_date = DateTimeProperty()


class ReportingMetadata(DocumentSchema):
    last_submissions = SchemaListProperty(LastSubmission)
    last_submission_for_user = SchemaProperty(LastSubmission)
    last_syncs = SchemaListProperty(LastSync)
    last_sync_for_user = SchemaProperty(LastSync)
    last_builds = SchemaListProperty(LastBuild)
    last_build_for_user = SchemaProperty(LastBuild)


class CouchUser(Document, DjangoUserMixin, IsMemberOfMixin, EulaMixin):
    """
    A user (for web and commcare)
    """
    base_doc = 'CouchUser'

    # todo: it looks like this is only ever set to a useless string and we should probably just remove it
    # https://github.com/dimagi/commcare-hq/pull/14087#discussion_r90423396
    device_ids = ListProperty()

    # this is the real list of devices
    devices = SchemaListProperty(DeviceIdLastUsed)
    # most recent device with most recent app for easy reporting
    last_device = SchemaProperty(DeviceIdLastUsed)

    phone_numbers = ListProperty()
    created_on = DateTimeProperty(default=datetime(year=1900, month=1, day=1))
    last_modified = DateTimeProperty()
    #    For now, 'status' is things like:
    #        ('auto_created',     'Automatically created from form submission.'),
    #        ('phone_registered', 'Registered from phone'),
    #        ('site_edited',     'Manually added or edited from the HQ website.'),
    status = StringProperty()
    language = StringProperty()
    subscribed_to_commcare_users = BooleanProperty(default=False)
    announcements_seen = ListProperty()
    user_data = DictProperty()      # use get_user_data object instead of accessing this directly
    # This should not be set directly but using set_location method only
    location_id = StringProperty()
    assigned_location_ids = StringListProperty()
    has_built_app = BooleanProperty(default=False)
    analytics_enabled = BooleanProperty(default=True)

    two_factor_auth_disabled_until = DateTimeProperty()
    login_attempts = IntegerProperty(default=0)
    attempt_date = DateProperty()

    reporting_metadata = SchemaProperty(ReportingMetadata)

    _user = None

    can_assign_superuser = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data, should_save=False):
        if "organizations" in data:
            del data["organizations"]
            should_save = True

        data = cls.migrate_eula(data)

        couch_user = super(CouchUser, cls).wrap(data)
        if should_save:
            couch_user.save()

        return couch_user

    class AccountTypeError(Exception):
        pass

    class Inconsistent(Exception):
        pass

    class InvalidID(Exception):
        pass

    class UnsuportedOperation(Exception):
        pass

    def __repr__(self):
        # copied from jsonobject/base.py
        name = self.__class__.__name__
        predefined_properties = set(self._properties_by_attr)
        predefined_property_keys = set(self._properties_by_attr[p].name
                                       for p in predefined_properties)
        dynamic_properties = set(self._wrapped) - predefined_property_keys

        # redact hashed password
        properties = sorted(predefined_properties - {'password'}) + sorted(dynamic_properties - {'password'})

        return '{name}({keyword_args})'.format(
            name=name,
            keyword_args=', '.join('{key}={value!r}'.format(
                key=key,
                value=getattr(self, key)
            ) for key in properties),
        )

    @property
    def two_factor_disabled(self):
        return (
            self.two_factor_auth_disabled_until
            and datetime.utcnow() < self.two_factor_auth_disabled_until
        )

    @property
    def is_dimagi(self):
        return is_dimagi_email(self.username)

    def is_locked_out(self):
        return self.supports_lockout() and self.should_be_locked_out()

    def should_be_locked_out(self):
        max_attempts = MAX_WEB_USER_LOGIN_ATTEMPTS if self.is_web_user() else MAX_COMMCARE_USER_LOGIN_ATTEMPTS
        return self.login_attempts >= max_attempts

    def supports_lockout(self):
        return True

    @property
    def raw_username(self):
        if self.doc_type == "CommCareUser":
            return self.username.split("@")[0]
        else:
            return self.username

    @property
    def username_in_report(self):
        return user_display_string(self.username, self.first_name, self.last_name)

    def html_username(self):
        username, *remaining = self.raw_username.split('@')
        if remaining:
            domain_name = remaining[0]
            html = format_html(
                '<span class="user_username">{}</span><span class="user_domainname">@{}</span>',
                username,
                domain_name)
        else:
            html = format_html("<span class='user_username'>{}</span>", username)
        return html

    @property
    def userID(self):
        return self._id

    user_id = userID

    def __str__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.get_id)

    def get_email(self):
        # Do not change the name of this method because this ends up implementing
        # get_email() from the CommCareMobileContactMixin for the CommCareUser
        return self.email

    def is_commcare_user(self):
        return self._get_user_type() == COMMCARE_USER

    def is_web_user(self):
        return self._get_user_type() == WEB_USER

    def _get_user_type(self):
        if self.doc_type == 'WebUser':
            return WEB_USER
        elif self.doc_type == 'CommCareUser':
            return COMMCARE_USER
        else:
            raise NotImplementedError(f'Unrecognized user type {self.doc_type!r}')

    @property
    def full_name(self):
        return ("%s %s" % (self.first_name or '', self.last_name or '')).strip()

    @property
    def human_friendly_name(self):
        return self.full_name if self.full_name else self.raw_username

    @property
    def name_in_filters(self):
        username = self.username.split("@")[0]
        return "%s <%s>" % (self.full_name, username) if self.full_name else username

    @property
    def days_since_created(self):
        # Note this does not round, but returns the floor of days since creation
        return (datetime.utcnow() - self.created_on).days

    @property
    def timestamp_created(self):
        return get_timestamp(self.created_on)

    formatted_name = full_name
    name = full_name

    def set_full_name(self, full_name):
        data = full_name.split()
        self.first_name = data.pop(0)
        self.last_name = ' '.join(data)

    def get_user_data(self, domain):
        # To do this in bulk, try UserData's prime_user_data_caches
        from .user_data import UserData
        if domain not in self._user_data_accessors:
            self._user_data_accessors[domain] = UserData.for_user(self, domain)
        return self._user_data_accessors[domain]

    def _save_user_data(self):
        for user_data in self._user_data_accessors.values():
            user_data.save()

    def get_user_session_data(self, domain):
        from corehq.apps.custom_data_fields.models import (
            SYSTEM_PREFIX,
            COMMCARE_USER_TYPE_KEY,
            COMMCARE_USER_TYPE_DEMO,
        )

        session_data = self.get_user_data(domain).to_dict()

        if self.is_commcare_user() and self.is_demo_user:
            session_data[COMMCARE_USER_TYPE_KEY] = COMMCARE_USER_TYPE_DEMO

        if self.is_web_user():
            # TODO can we do this for both types of users and remove the fields from user data?
            session_data['commcare_location_id'] = self.get_location_id(domain)
            session_data['commcare_location_ids'] = user_location_data(self.get_location_ids(domain))

        session_data.update({
            f'{SYSTEM_PREFIX}_first_name': self.first_name,
            f'{SYSTEM_PREFIX}_last_name': self.last_name,
            f'{SYSTEM_PREFIX}_phone_number': self.phone_number,
            f'{SYSTEM_PREFIX}_user_type': self._get_user_type(),
        })
        return session_data

    def _get_case_owning_locations(self, domain):
        """
        :return: queryset of case-owning locations either directly assigned to the
        user or descendant from an assigned location that views descendants
        """
        from corehq.apps.locations.models import SQLLocation

        yield from self.get_sql_locations(domain).filter(location_type__shares_cases=True)

        yield from SQLLocation.objects.get_queryset_descendants(
            self.get_sql_locations(domain).filter(location_type__view_descendants=True)
        ).filter(location_type__shares_cases=True, is_archived=False)

    def delete(self, deleted_by_domain, deleted_by, deleted_via=None):
        from corehq.apps.users.model_log import UserModelAction

        if not deleted_by and not settings.UNIT_TESTING:
            raise ValueError("Missing deleted_by")
        self.clear_quickcache_for_user()
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
        if deleted_by:
            # Commcare user is owned by the domain it belongs to so use self.domain for for_domain
            # Web user is never deleted except in tests so keep for_domain as None
            if self.is_commcare_user():
                for_domain = self.domain
                for_domain_required_for_log = True
            else:
                for_domain = None
                for_domain_required_for_log = False
            log_user_change(by_domain=deleted_by_domain, for_domain=for_domain,
                            couch_user=self, changed_by_user=deleted_by,
                            changed_via=deleted_via, action=UserModelAction.DELETE,
                            for_domain_required_for_log=for_domain_required_for_log)
        super(CouchUser, self).delete()  # Call the "real" delete() method.

    def delete_phone_number(self, phone_number):
        for i in range(0, len(self.phone_numbers)):
            if self.phone_numbers[i] == phone_number:
                del self.phone_numbers[i]
                break
        self.save()
        self.delete_phone_entry(phone_number)

    def get_django_user(self, use_primary_db=False):
        queryset = User.objects
        if use_primary_db:
            queryset = queryset.using(router.db_for_write(User))
        return queryset.get(username=self.username)

    def add_phone_number(self, phone_number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(phone_number, str):
            phone_number = str(phone_number)
        self.phone_numbers = _add_to_list(self.phone_numbers, phone_number, default)

    def set_default_phone_number(self, phone_number):
        self.add_phone_number(phone_number, True)
        self.save()

    def set_phone_numbers(self, new_phone_numbers, default_number=''):
        self.phone_numbers = list(set(new_phone_numbers))  # ensure uniqueness
        if default_number:
            self.add_phone_number(default_number, True)

    @property
    def default_phone_number(self):
        return _get_default(self.phone_numbers)
    phone_number = default_phone_number

    def phone_numbers_extended(self, requesting_user):
        """
        Returns information about the status of each of this user's phone numbers.
        requesting_user - The user that is requesting this information (from a view)
        """
        from corehq.apps.sms.models import PhoneNumber
        from corehq.apps.hqwebapp.doc_info import get_object_url

        phone_entries = self.get_phone_entries()

        def get_phone_info(phone):
            info = {}
            phone_entry = phone_entries.get(apply_leniency(phone))

            if phone_entry and phone_entry.verified:
                status = 'verified'
            elif phone_entry and phone_entry.pending_verification:
                status = 'pending'
            else:
                duplicate = PhoneNumber.get_reserved_number(phone)
                if duplicate:
                    status = 'duplicate'
                    if requesting_user.is_member_of(duplicate.domain):
                        info['dup_url'] = get_object_url(duplicate.domain,
                            duplicate.owner_doc_type, duplicate.owner_id)
                else:
                    status = 'unverified'

            info.update({'number': phone, 'status': status})
            return info

        return [get_phone_info(phone) for phone in self.phone_numbers]

    @property
    def couch_id(self):
        return self._id

    # Couch view wrappers
    @classmethod
    def all(cls):
        return CouchUser.view("users/by_username", include_docs=True, reduce=False)

    @classmethod
    def username_exists(cls, username):
        reduced = cls.view('users/by_username', key=username, reduce=True).all()
        if reduced:
            return reduced[0]['value'] > 0
        return False

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

        return cls.view(
            "users/by_domain",
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
        return (self.is_superuser
                or bool(re.compile(settings.PREVIEWER_RE).match(self.username)))

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
            attr_val = getattr(self, attr)
            if attr in [
                'is_active',
                'is_staff',
                'is_superuser',
            ]:
                attr_val = attr_val if attr_val is True else False
            elif not attr_val and attr != 'last_login':
                attr_val = ''
            # truncate names when saving to django
            if attr == 'first_name' or attr == 'last_name':
                attr_val = attr_val[:30]
            setattr(django_user, attr, attr_val)
        django_user.DO_NOT_SAVE_COUCH_USER = True
        return django_user

    @classmethod
    def wrap_correctly(cls, source, allow_deleted_doc_types=False):
        try:
            doc_type = source['doc_type']
        except KeyError as err:
            raise KeyError(f"'doc_type' not found in {source!r}") from err
        if allow_deleted_doc_types:
            doc_type = doc_type.replace(DELETED_SUFFIX, '')

        return {
            'WebUser': WebUser,
            'CommCareUser': CommCareUser,
            'FakeUser': FakeUser,
        }[doc_type].wrap(source)

    @classmethod
    @quickcache(['username'], skip_arg="strict")
    def get_by_username(cls, username, strict=False):
        if not username:
            return None

        view_result = cls.get_db().view(
            'users/by_username',
            key=username,
            include_docs=True,
            reduce=False,
        )
        result = view_result.all()
        if len(result) > 1:
            raise MultipleResultsFound('"{}": {}'.format(
                username, ', '.join([row['id'] for row in result])
            ))
        result = result[0] if result else None
        if result and result['doc'] and result['doc']['username'] == username:
            couch_user = cls.wrap_correctly(result['doc'])
            cls.get_by_user_id.set_cached_value(couch_user.__class__, couch_user.get_id).to(couch_user)
            return couch_user
        else:
            return None

    def clear_quickcache_for_user(self):
        from corehq.apps.domain.views.base import (
            get_domain_links_for_dropdown,
            get_enterprise_links_for_dropdown,
        )
        from corehq.apps.sms.util import is_user_contact_active

        self.get_by_username.clear(self.__class__, self.username)
        self.get_by_user_id.clear(self.__class__, self.user_id)
        username_to_user_id.clear(self.username)
        domains = getattr(self, 'domains', None)
        if domains is None:
            domain = getattr(self, 'domain', None)
            domains = [domain] if domain else []
        for domain in domains:
            self.get_by_user_id.clear(self.__class__, self.user_id, domain)
            is_user_contact_active.clear(domain, self.user_id)
        Domain.active_for_couch_user.clear(self)
        get_domain_links_for_dropdown.clear(self)
        get_enterprise_links_for_dropdown.clear(self)

    @classmethod
    @quickcache(['userID', 'domain'])
    def get_by_user_id(cls, userID, domain=None):
        """
        if domain is given, checks to make sure the user is a member of that domain
        returns None if there's no user found or if the domain check fails
        """
        try:
            couch_user = cls.wrap_correctly(cls.get_db().get(userID))
        except ResourceNotFound:
            return None
        if couch_user.doc_type != cls.__name__ and cls.__name__ != "CouchUser":
            raise CouchUser.AccountTypeError()
        if domain:
            if not couch_user.is_member_of(domain):
                return None
        cls.get_by_username.set_cached_value(couch_user.__class__, couch_user.username).to(couch_user)
        return couch_user

    @classmethod
    def from_django_user(cls, django_user, strict=False):
        return cls.get_by_username(django_user.username, strict=strict)

    def __init__(self, *args, **kwargs):
        self._user_data_accessors = {}
        super().__init__(*args, **kwargs)

    @classmethod
    def create(cls, domain, username, password, created_by, created_via, email=None, uuid='', date='',
               user_data=None, first_name='', last_name='', **kwargs):
        try:
            django_user = User.objects.using(router.db_for_write(User)).get(username=username)
        except User.DoesNotExist:
            django_user = create_user(
                username, password=password, email=email,
                first_name=first_name, last_name=last_name, **kwargs
            )

        if uuid:
            if not re.match(r'[\w-]+', uuid):
                raise cls.InvalidID('invalid id %r' % uuid)
        else:
            uuid = uuid4().hex
        couch_user = cls(_id=uuid)

        if date:
            couch_user.created_on = force_to_datetime(date)
        else:
            couch_user.created_on = datetime.utcnow()

        couch_user.sync_from_django_user(django_user)

        if user_data:
            couch_user.get_user_data(domain).update(user_data)

        return couch_user

    def to_be_deleted(self):
        return self.base_doc.endswith(DELETED_SUFFIX)

    @classmethod
    def save_docs(cls, docs, **kwargs):
        utcnow = datetime.utcnow()
        for doc in docs:
            doc['last_modified'] = utcnow
        super(CouchUser, cls).save_docs(docs, **kwargs)
        for user in docs:
            user.clear_quickcache_for_user()

    bulk_save = save_docs

    def save(self, fire_signals=True, update_django_user=True, fail_hard=False, **params):
        # fail_hard determines whether the save should fail if it cannot obtain the critical section
        # historically, the critical section hasn't been enforced, but enforcing it is a dramatic change
        # for our system. The goal here is to allow the programmer to specify fail_hard on a workflow-by-workflow
        # basis, so we can gradually shift to all saves requiring the critical section.

        # HEADS UP!
        # When updating this method, please also ensure that your updates also
        # carry over to bulk_auto_deactivate_commcare_users.
        self.last_modified = datetime.utcnow()
        with CriticalSection(['username-check-%s' % self.username], fail_hard=fail_hard, timeout=120):
            # test no username conflict
            by_username = self.get_db().view('users/by_username', key=self.username, reduce=False).first()
            if by_username and by_username['id'] != self._id:
                raise self.Inconsistent("CouchUser with username %s already exists" % self.username)

            if update_django_user and self._rev and not self.to_be_deleted():
                django_user = self.sync_to_django_user()
                django_user.save()

            if not self.to_be_deleted():
                self._save_user_data()
            try:
                super(CouchUser, self).save(**params)
            finally:
                # ensure the cache is cleared even if something goes wrong while saving the user to couch
                self.clear_quickcache_for_user()

        if fire_signals:
            self.fire_signals()

    def fire_signals(self):
        from .signals import couch_user_post_save
        results = couch_user_post_save.send_robust(sender='couch_user', couch_user=self)
        log_signal_errors(results, "Error occurred while syncing user (%s)", {'username': self.username})

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
                    if max_tries > 0:
                        couch_user.clear_quickcache_for_user()
                        cls.django_user_post_save_signal(sender, django_user, created, max_tries - 1)
                    else:
                        raise

                couch_user.clear_quickcache_for_user()

    def is_deleted(self):
        return self.base_doc.endswith(DELETED_SUFFIX)

    def get_viewable_reports(self, domain=None, name=False, slug=False):
        def slug_name(model):
            try:
                if slug:
                    return to_function(model).slug
                if name:
                    return to_function(model).name
            except AttributeError:
                logging.warning("Unable to load report model: %s", model)
                return None

        models = self._get_viewable_report_slugs(domain)
        if slug or name:
            return [_f for _f in [slug_name(m) for m in models] if _f]

        return models

    def _get_viewable_report_slugs(self, domain):
        domain = domain or getattr(self, 'current_domain', None)

        if self.is_commcare_user():
            role = self.get_role(domain)
            if role is None:
                return []
            else:
                return role.permissions.view_report_list
        else:
            dm = self.get_domain_membership(domain, allow_enterprise=True)
            return dm.viewable_reports() if dm else []

    def can_view_some_reports(self, domain):
        return self.can_view_reports(domain) or bool(self.get_viewable_reports(domain))

    def can_access_any_exports(self, domain=None):
        return self.can_view_reports(domain) or any([
            permission_slug for permission_slug in self._get_viewable_report_slugs(domain)
            if permission_slug in EXPORT_PERMISSIONS
        ])

    def can_view_some_tableau_viz(self, domain):
        if not self.can_access_all_locations(domain):
            return False

        from corehq.apps.reports.models import TableauVisualization
        return self.can_view_tableau(domain) or bool(TableauVisualization.for_user(domain, self))

    def can_login_as(self, domain):
        return (
            self.has_permission(domain, 'login_as_all_users')
            or self.has_permission(domain, 'limited_login_as')
        )

    def can_manage_events(self, domain):
        return self.has_permission(domain, 'manage_attendance_tracking')

    def is_current_web_user(self, request):
        return self.user_id == request.couch_user.user_id

    # gets hit for can_view_reports, etc.
    def __getattr__(self, item):
        if item.startswith('can_'):
            perm = item[len('can_'):]
            if perm:
                fn = self._get_perm_check_fn(perm)
                fn.__name__ = item
                return fn

        raise AttributeError("'{}' object has no attribute '{}'".format(
            self.__class__.__name__, item))

    def _get_perm_check_fn(self, perm):
        def fn(domain=None, data=None):
            domain = domain or getattr(self, 'current_domain', None)
            return self.has_permission(domain, perm, data)
        return fn

    def get_location_id(self, domain):
        return getattr(self.get_domain_membership(domain), 'location_id', None)

    def set_has_built_app(self):
        if not self.has_built_app:
            self.has_built_app = True
            self.save()

    def log_user_create(self, domain, created_by, created_via, by_domain_required_for_log=True):
        from corehq.apps.users.model_log import UserModelAction

        if settings.UNIT_TESTING and created_by is None and created_via is None:
            return
        # fallback to self if not created by any user
        created_by = created_by or self
        # Commcare user is owned by the domain it belongs to so use self.domain for for_domain
        # Web user is not "created" by a domain but invited so keep for_domain as None
        if self.is_commcare_user():
            for_domain = self.domain
            for_domain_required_for_log = True
        else:
            for_domain = None
            for_domain_required_for_log = False
        log_user_change(
            by_domain=domain,
            for_domain=for_domain,
            couch_user=self,
            changed_by_user=created_by,
            changed_via=created_via,
            action=UserModelAction.CREATE,
            by_domain_required_for_log=by_domain_required_for_log,
            for_domain_required_for_log=for_domain_required_for_log
        )

    def belongs_to_messaging_domain(self):
        domains = (Domain.get_by_name(domain) for domain in self.domains)

        # The reason we iterate through domains, rather than fetch them all at once (there is a view to do so)
        # is due to concerns about scale. Most users belong to one or a few domains, so iteration isn't expensive.
        # For users that DO belong to many domains, I'm working off the assumption that most of them are for
        # enterprise domains, which have turned on messaging for most of their domains -- so we likely will
        # short-circuit after only a few domains
        return any(domain.granted_messaging_access for domain in domains)


class CommCareUser(CouchUser, SingleMembershipMixin, CommCareMobileContactMixin):
    domain = StringProperty()
    registering_device_id = StringProperty()
    # used by loadtesting framework - should typically be empty
    loadtest_factor = IntegerProperty()
    is_loadtest_user = BooleanProperty(default=False)
    is_demo_user = BooleanProperty(default=False)
    demo_restore_id = IntegerProperty()
    # used by user provisioning workflow. defaults to true unless explicitly overridden during
    # user creation
    is_account_confirmed = BooleanProperty(default=True)

    # This means that this user represents a location, and has a 1-1 relationship
    # with a location where location.location_type.has_user == True
    user_location_id = StringProperty()

    @classmethod
    def wrap(cls, data):
        # migrations from using role_id to using the domain_memberships
        role_id = None
        if 'role_id' in data:
            role_id = data["role_id"]
            del data['role_id']
        if not data.get('domain_membership', {}).get('domain', None):
            data['domain_membership'] = DomainMembership(
                domain=data.get('domain', ""), role_id=role_id
            ).to_json()
        return super(CommCareUser, cls).wrap(data)

    def _is_demo_user_cached_value_is_stale(self):
        from corehq.apps.users.dbaccessors import get_practice_mode_mobile_workers
        cached_demo_users = get_practice_mode_mobile_workers.get_cached_value(self.domain)
        if cached_demo_users is not Ellipsis:
            cached_is_demo_user = any(user['_id'] == self._id for user in cached_demo_users)
            if cached_is_demo_user != self.is_demo_user:
                return True
        return False

    def clear_quickcache_for_user(self):
        from corehq.apps.users.dbaccessors import get_practice_mode_mobile_workers
        self.get_usercase_id.clear(self)
        get_loadtest_factor_for_restore_cache_key.clear(self.domain, self.user_id)

        if self._is_demo_user_cached_value_is_stale():
            get_practice_mode_mobile_workers.clear(self.domain)
        super(CommCareUser, self).clear_quickcache_for_user()

    def save(self, fire_signals=True, spawn_task=False, **params):
        is_new_user = self.new_document  # before saving, check if this is a new document
        super(CommCareUser, self).save(fire_signals=fire_signals, **params)

        if fire_signals:
            from corehq.apps.callcenter.tasks import sync_usercases_if_applicable
            from .signals import commcare_user_post_save
            results = commcare_user_post_save.send_robust(sender='couch_user', couch_user=self,
                                                          is_new_user=is_new_user)
            log_signal_errors(results, "Error occurred while syncing user (%s)", {'username': self.username})
            if not self.to_be_deleted():
                sync_usercases_if_applicable(self, spawn_task)

    def delete(self, deleted_by_domain, deleted_by, deleted_via=None):
        from corehq.apps.ota.utils import delete_demo_restore_for_user
        # clear demo restore objects if any
        delete_demo_restore_for_user(self)

        super(CommCareUser, self).delete(deleted_by_domain, deleted_by=deleted_by, deleted_via=deleted_via)

    @property
    def project(self):
        return Domain.get_by_name(self.domain)

    def is_domain_admin(self, domain=None):
        # cloudcare workaround
        return False

    @classmethod
    def create(cls,
               domain,
               username,
               password,
               created_by,
               created_via,
               email=None,
               uuid='',
               date='',
               phone_number=None,
               location=None,
               commit=True,
               is_account_confirmed=True,
               user_data=None,
               **kwargs):
        """
        Main entry point into creating a CommCareUser (mobile worker).
        """
        # if the account is not confirmed, also set is_active false so they can't login
        if 'is_active' not in kwargs:
            kwargs['is_active'] = is_account_confirmed
        elif not is_account_confirmed:
            assert not kwargs['is_active'], \
                "it's illegal to create a user with is_active=True and is_account_confirmed=False"
        commcare_user = super(CommCareUser, cls).create(domain, username, password, created_by, created_via,
                                                        email, uuid, date, user_data, **kwargs)
        if phone_number is not None:
            commcare_user.add_phone_number(phone_number)

        device_id = kwargs.get('device_id', '')
        # populate the couch user
        commcare_user.domain = domain
        commcare_user.device_ids = [device_id]
        commcare_user.registering_device_id = device_id
        commcare_user.is_account_confirmed = is_account_confirmed
        commcare_user.domain_membership = DomainMembership(domain=domain, **kwargs)

        if location:
            commcare_user.set_location(location, commit=False)

        if commit:
            commcare_user.save(**get_safe_write_kwargs())
            commcare_user.log_user_create(domain, created_by, created_via)
        return commcare_user

    @property
    def filter_flag(self):
        from corehq.apps.reports.models import HQUserType
        return HQUserType.ACTIVE

    def is_commcare_user(self):
        return True

    def is_web_user(self):
        return False

    def supports_lockout(self):
        return not self.project.disable_mobile_login_lockout

    def to_ota_restore_user(self, domain, request_user=None):
        assert domain == self.domain
        return OTARestoreCommCareUser(
            self.domain,
            self,
            loadtest_factor=self.loadtest_factor or 1,
            request_user=request_user,
        )

    def _get_form_ids(self):
        return XFormInstance.objects.get_form_ids_for_user(self.domain, self.user_id)

    def _get_case_ids(self):
        return CommCareCase.objects.get_case_ids_in_domain_by_owners(self.domain, [self.user_id])

    def _get_deleted_form_ids(self):
        return XFormInstance.objects.get_deleted_form_ids_for_user(self.domain, self.user_id)

    def _get_deleted_case_ids(self):
        return CommCareCase.objects.get_deleted_case_ids_by_owner(self.domain, self.user_id)

    def get_owner_ids(self, domain):
        owner_ids = [self.user_id]
        owner_ids.extend(g._id for g in self.get_case_sharing_groups())
        return owner_ids

    def unretire(self, unretired_by_domain, unretired_by, unretired_via=None):
        """
        This un-deletes a user, but does not fully restore the state to
        how it previously was. Using this has these caveats:
        - It will not restore Case Indexes that were removed
        - It will not restore the user's phone numbers
        - It will not restore reminders for cases
        - It will not restore custom user data
        """
        from corehq.apps.users.model_log import UserModelAction

        if not unretired_by and not settings.UNIT_TESTING:
            raise ValueError("Missing unretired_by")

        by_username = self.get_db().view('users/by_username', key=self.username, reduce=False).first()
        if by_username and by_username['id'] != self._id:
            return False, "A user with the same username already exists in the system"
        if self.base_doc.endswith(DELETED_SUFFIX):
            self.base_doc = self.base_doc[:-len(DELETED_SUFFIX)]

        deleted_form_ids = self._get_deleted_form_ids()
        XFormInstance.objects.soft_undelete_forms(self.domain, deleted_form_ids)

        deleted_case_ids = self._get_deleted_case_ids()
        CommCareCase.objects.soft_undelete_cases(self.domain, deleted_case_ids)

        undelete_system_forms.delay(self.domain, set(deleted_form_ids), set(deleted_case_ids))
        self.save()
        if unretired_by:
            log_user_change(
                by_domain=unretired_by_domain,
                for_domain=self.domain,
                couch_user=self,
                changed_by_user=unretired_by,
                changed_via=unretired_via,
                action=UserModelAction.CREATE,
            )
        return True, None

    def retire(self, retired_by_domain, deleted_by, deleted_via=None):
        from corehq.apps.users.model_log import UserModelAction

        if not deleted_by and not settings.UNIT_TESTING:
            raise ValueError("Missing deleted_by")

        deletion_id, deletion_date = self.delete_user_data()
        suffix = DELETED_SUFFIX

        # doc_type remains the same, since the views use base_doc instead
        if not self.base_doc.endswith(suffix):
            self.base_doc += suffix
            self['-deletion_id'] = deletion_id
            self['-deletion_date'] = deletion_date

        try:
            django_user = self.get_django_user()
        except User.DoesNotExist:
            pass
        else:
            django_user.delete()
        if deleted_by:
            log_user_change(by_domain=retired_by_domain, for_domain=self.domain,
                            couch_user=self, changed_by_user=deleted_by,
                            changed_via=deleted_via, action=UserModelAction.DELETE)
        self.save()

    def delete_user_data(self):
        deletion_id = uuid4().hex
        deletion_date = datetime.utcnow()

        deleted_cases = set()
        for case_id_list in chunked(self._get_case_ids(), 50):
            tag_cases_as_deleted_and_remove_indices.delay(self.domain, case_id_list, deletion_id, deletion_date)
            deleted_cases.update(case_id_list)

        deleted_forms = set()
        for form_id_list in chunked(self._get_form_ids(), 50):
            tag_forms_as_deleted_rebuild_associated_cases.delay(
                self.user_id, self.domain, form_id_list, deletion_id, deletion_date, deleted_cases=deleted_cases
            )
            deleted_forms.update(form_id_list)

        tag_system_forms_as_deleted.delay(self.domain, deleted_forms, deleted_cases, deletion_id, deletion_date)

        from corehq.apps.app_manager.views.utils import unset_practice_mode_configured_apps
        unset_practice_mode_configured_apps(self.domain, self.get_id)

        return deletion_id, deletion_date

    def confirm_account(self, password):
        if self.is_account_confirmed:
            raise IllegalAccountConfirmation('Account is already confirmed')
        assert not self.is_active, 'Active account should not be unconfirmed!'
        self.is_active = True
        self.is_account_confirmed = True
        self.set_password(password)
        self.save()

    def get_case_sharing_groups(self):
        from corehq.apps.groups.models import Group
        from corehq.apps.events.models import (
            get_user_case_sharing_groups_for_events,
        )

        # get faked location group objects
        groups = [
            location.case_sharing_group_object(self._id)
            for location in self._get_case_owning_locations(self.domain)
        ]
        groups += [group for group in Group.by_user_id(self._id) if group.case_sharing]

        has_at_privilege = domain_has_privilege(self.domain, privileges.ATTENDANCE_TRACKING)
        # Temporary toggle that will be removed once the feature is released
        has_at_toggle_enabled = toggles.ATTENDANCE_TRACKING.enabled(self.domain)
        if has_at_privilege and has_at_toggle_enabled:
            groups += get_user_case_sharing_groups_for_events(self)
        return groups

    def get_reporting_groups(self):
        from corehq.apps.groups.models import Group
        return [group for group in Group.by_user_id(self._id) if group.reporting]

    def get_group_ids(self):
        from corehq.apps.groups.models import Group
        return Group.by_user_id(self._id, wrap=False)

    def set_groups(self, group_ids):
        """
        :returns: True if groups were updated
        """
        from corehq.apps.groups.models import Group
        desired = set(group_ids)
        current = set(self.get_group_ids())
        touched = []
        faulty_groups = []
        for to_add in desired - current:
            group = Group.get(to_add)
            if group.domain != self.domain:
                faulty_groups.append(to_add)
                continue
            group.add_user(self._id, save=False)
            touched.append(group)
        if faulty_groups:
            raise ValidationError("Unable to save groups. The following group_ids are not in the current domain: "
                                  + ', '.join(faulty_groups))
        for to_remove in current - desired:
            group = Group.get(to_remove)
            group.remove_user(self._id)
            touched.append(group)

        Group.bulk_save(touched)
        return bool(touched)

    def get_time_zone(self):
        if self.memoized_usercase:
            return self.memoized_usercase.get_time_zone()

        return None

    def get_language_code(self):
        if self.language:
            return self.language

        if self.memoized_usercase:
            return self.memoized_usercase.get_language_code()

        return None

    @property
    @memoized
    def location(self):
        return self.sql_location

    @property
    def sql_location(self):
        from corehq.apps.locations.models import SQLLocation
        if self.location_id:
            return SQLLocation.objects.get_or_None(location_id=self.location_id)
        return None

    def get_location_ids(self, domain):
        # domain arg included here for compatibility with WebUser
        return self.assigned_location_ids

    def get_sql_locations(self, domain):
        # domain arg included here for compatibility with WebUser
        from corehq.apps.locations.models import SQLLocation
        if self.assigned_location_ids:
            return SQLLocation.objects.filter(location_id__in=self.assigned_location_ids)
        else:
            return SQLLocation.objects.none()

    def add_to_assigned_locations(self, location, commit=True):
        if self.location_id:
            if location.location_id in self.assigned_location_ids:
                return
            self.assigned_location_ids.append(location.location_id)
            self.get_domain_membership(self.domain).assigned_location_ids.append(location.location_id)
            user_data = self.get_user_data(self.domain)
            user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
            if commit:
                self.save()
        else:
            self.set_location(location, commit=commit)

    @memoized
    def get_sql_location(self, domain):
        return self.sql_location

    def set_location(self, location, commit=True):
        """
        Set the primary location, and all important user data, for
        the user.

        :param location: may be a sql or couch location
        """
        from corehq.apps.fixtures.models import UserLookupTableType

        if not location.location_id:
            raise AssertionError("You can't set an unsaved location")

        user_data = self.get_user_data(self.domain)
        user_data['commcare_location_id'] = location.location_id

        if not location.location_type.administrative:
            # just need to trigger a get or create to make sure
            # this exists, otherwise things blow up
            sp = SupplyInterface(self.domain).get_or_create_by_location(location)
            user_data['commtrack-supply-point'] = sp.case_id

        self.create_location_delegates([location])

        user_data['commcare_primary_case_sharing_id'] = location.location_id
        self.update_fixture_status(UserLookupTableType.LOCATION)
        self.location_id = location.location_id
        self.get_domain_membership(self.domain).location_id = location.location_id
        if self.location_id not in self.assigned_location_ids:
            self.assigned_location_ids.append(self.location_id)
            self.get_domain_membership(self.domain).assigned_location_ids.append(self.location_id)
            user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
        self.get_sql_location.reset_cache(self)
        if commit:
            self.save()

    def unset_location(self, fall_back_to_next=False, commit=True):
        """
        Resets primary location to next available location from assigned_location_ids.
            If there are no more locations in assigned_location_ids,
            then the primary location and user data are cleared

            If fall_back_to_next is True, primary location is not set to next but cleared.
            This option exists only to be backwards compatible when user can only have one location
        """
        from corehq.apps.fixtures.models import UserLookupTableType
        from corehq.apps.locations.models import SQLLocation
        old_primary_location_id = self.location_id
        if old_primary_location_id:
            self._remove_location_from_user(old_primary_location_id)

        user_data = self.get_user_data(self.domain)
        if self.assigned_location_ids:
            user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
        elif user_data.get('commcare_location_ids', None):
            del user_data['commcare_location_ids']

        if self.assigned_location_ids and fall_back_to_next:
            new_primary_location_id = self.assigned_location_ids[0]
            self.set_location(SQLLocation.objects.get(location_id=new_primary_location_id))
        else:
            user_data.pop('commcare_location_id', None)
            user_data.pop('commtrack-supply-point', None)
            user_data.pop('commcare_primary_case_sharing_id', None)
            self.location_id = None
            self.clear_location_delegates()
            self.update_fixture_status(UserLookupTableType.LOCATION)
            self.get_domain_membership(self.domain).location_id = None
            self.get_sql_location.reset_cache(self)
            if commit:
                self.save()

    def unset_location_by_id(self, location_id, fall_back_to_next=False):
        """
        Unset a location that the user is assigned to that may or may not be primary location.
            If the location_id is primary-location, then next available location from
            assigned_location_ids is set as the primary-location.
            If fall_back_to_next is True, primary location is not set to next
        """
        if location_id == self.location_id:
            # check if primary location
            self.unset_location(fall_back_to_next)
        else:
            self._remove_location_from_user(location_id)

            user_data = self.get_user_data(self.domain)
            if self.assigned_location_ids:
                user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
            else:
                user_data.pop('commcare_location_ids', None)
            self.save()

    def _remove_location_from_user(self, location_id):
        from corehq.apps.fixtures.models import UserLookupTableType
        try:
            self.assigned_location_ids.remove(location_id)
            self.update_fixture_status(UserLookupTableType.LOCATION)
        except ValueError:
            notify_exception(None, "Location missing from user", {
                'user_id': self._id,
                'location_id': location_id
            })
        try:
            self.get_domain_membership(self.domain).assigned_location_ids.remove(location_id)
        except ValueError:
            notify_exception(None, "Location missing from domain membership", {
                'user_id': self._id,
                'location_id': location_id
            })

    def reset_locations(self, location_ids, commit=True):
        """
        Reset user's assigned_locations to given location_ids and update user data.
            This should be called after updating primary location via set_location/unset_location
            If primary-location is not set, then next available location from
            assigned_location_ids is set as the primary-location
        """
        from corehq.apps.locations.models import SQLLocation

        self.assigned_location_ids = location_ids
        self.get_domain_membership(self.domain).assigned_location_ids = location_ids
        user_data = self.get_user_data(self.domain)
        if location_ids:
            user_data['commcare_location_ids'] = user_location_data(location_ids)
        else:
            user_data.pop('commcare_location_ids', None)

        # try to set primary-location if not set already
        if not self.location_id and location_ids:
            self.set_location(SQLLocation.objects.get(location_id=location_ids[0]), commit=False)

        if commit:
            self.save()

    def supply_point_index_mapping(self, supply_point, clear=False):
        from corehq.apps.commtrack.exceptions import (
            LinkedSupplyPointNotFoundError
        )

        if supply_point:
            return {
                'supply_point-' + supply_point.case_id:
                (
                    supply_point.type,
                    supply_point.case_id if not clear else ''
                )
            }
        else:
            raise LinkedSupplyPointNotFoundError(
                "There was no linked supply point for the location."
            )

    def submit_location_block(self, caseblock, source):
        from corehq.apps.hqcase.utils import submit_case_blocks

        submit_case_blocks(
            ElementTree.tostring(
                caseblock.as_xml(), encoding='utf-8'
            ).decode('utf-8'),
            self.domain,
            device_id=__name__ + ".CommCareUser." + source,
        )

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
        self.clear_location_delegates()

        if not locations:
            return

        index = {}
        for location in locations:
            if not location.location_type.administrative:
                sp = SupplyInterface(self.domain).get_by_location(location)
                index.update(self.supply_point_index_mapping(sp))

        from corehq.apps.commtrack.util import location_map_case_id
        caseblock = CaseBlock(
            create=True,
            case_type=USER_LOCATION_OWNER_MAP_TYPE,
            case_id=location_map_case_id(self),
            owner_id=self._id,
            index=index
        )

        self.submit_location_block(caseblock, "create_location_delegates")

    def get_location_map_case(self):
        """
        Returns the location mapping case for this supply point.

        That lets us give access to the supply point via
        delagate access.
        """
        try:
            from corehq.apps.commtrack.util import location_map_case_id
            return CommCareCase.objects.get_case(location_map_case_id(self), self.domain)
        except CaseNotFound:
            return None

    @property
    def fixture_statuses(self):
        """Returns all of the last modified times for each fixture type"""
        return get_fixture_statuses(self._id)

    def fixture_status(self, fixture_type):
        try:
            return self.fixture_statuses[fixture_type]
        except KeyError:
            from corehq.apps.fixtures.models import UserLookupTableStatus
            return UserLookupTableStatus.DEFAULT_LAST_MODIFIED

    def update_fixture_status(self, fixture_type):
        from corehq.apps.fixtures.models import UserLookupTableStatus
        now = datetime.utcnow()
        user_fixture_sync, new = UserLookupTableStatus.objects.get_or_create(
            user_id=self._id,
            fixture_type=fixture_type,
            defaults={'last_modified': now},
        )
        if not new:
            user_fixture_sync.last_modified = now
            user_fixture_sync.save()
        get_fixture_statuses.clear(self._id)

    def __repr__(self):
        return ("{class_name}(username={self.username!r})".format(
            class_name=self.__class__.__name__,
            self=self
        ))

    @property
    @memoized
    def memoized_usercase(self):
        return self.get_usercase()

    def get_usercase(self):
        return CommCareCase.objects.get_case_by_external_id(self.domain, self._id, USERCASE_TYPE)

    @quickcache(['self._id'], lambda _: settings.UNIT_TESTING)
    def get_usercase_id(self):
        case = self.get_usercase()
        return case.case_id if case else None

    def update_device_id_last_used(self, device_id, when=None, commcare_version=None, device_app_meta=None,
                                   fcm_token=None, fcm_token_timestamp=None):
        """
        Sets the last_used date for the device to be the current time
        Does NOT save the user object.

        :returns: True if user was updated and needs to be saved
        """
        when = when or datetime.utcnow()
        device = self.get_device(device_id)
        save_user = False
        if device:
            do_update = False
            if when.date() > device.last_used.date():
                do_update = True
            elif device_app_meta:
                existing_app_meta = device.get_meta_for_app(device_app_meta.app_id)
                if not existing_app_meta:
                    do_update = True
                else:
                    last_request = device_app_meta.last_request
                    do_update = (
                        last_request
                        and existing_app_meta.last_request
                        and last_request > existing_app_meta.last_request.date()
                    )

            if do_update:
                device.last_used = when
                device.update_meta(commcare_version, device_app_meta)

                self.last_device = DeviceIdLastUsed.wrap(self.get_last_used_device().to_json())
                meta = self.last_device.get_last_used_app_meta()
                self.last_device.app_meta = [meta] if meta else []
                save_user = True
            if fcm_token and fcm_token_timestamp:
                if not device.fcm_token_timestamp or fcm_token_timestamp > device.fcm_token_timestamp:
                    device.update_fcm_token(fcm_token, fcm_token_timestamp)
                    save_user = True
        else:
            device = DeviceIdLastUsed(device_id=device_id, last_used=when)
            if fcm_token and fcm_token_timestamp:
                device.update_fcm_token(fcm_token, fcm_token_timestamp)
            device.update_meta(commcare_version, device_app_meta)
            self.devices.append(device)
            self.last_device = device
            save_user = True
        return save_user

    def get_last_used_device(self):
        if not self.devices:
            return None

        return max(self.devices, key=lambda dev: dev.last_used)

    def get_device(self, device_id):
        for device in self.devices:
            if device.device_id == device_id:
                return device

    def get_devices_fcm_tokens(self):
        return [device.fcm_token for device in self.devices if device.fcm_token]


def update_fixture_status_for_users(user_ids, fixture_type):
    from corehq.apps.fixtures.models import UserLookupTableStatus
    from dimagi.utils.chunked import chunked

    now = datetime.utcnow()
    for ids in chunked(user_ids, 50):
        (UserLookupTableStatus.objects
         .filter(user_id__in=ids,
                 fixture_type=fixture_type)
         .update(last_modified=now))
    for user_id in user_ids:
        get_fixture_statuses.clear(user_id)


@quickcache(['user_id'], skip_arg=lambda user_id: settings.UNIT_TESTING)
def get_fixture_statuses(user_id):
    from corehq.apps.fixtures.models import UserLookupTableType, UserLookupTableStatus
    last_modifieds = {choice[0]: UserLookupTableStatus.DEFAULT_LAST_MODIFIED
                      for choice in UserLookupTableType.CHOICES}
    for fixture_status in UserLookupTableStatus.objects.filter(user_id=user_id):
        last_modifieds[fixture_status.fixture_type] = fixture_status.last_modified
    return last_modifieds


class WebUser(CouchUser, MultiMembershipMixin, CommCareMobileContactMixin):
    program_id = StringProperty()
    last_password_set = DateTimeProperty(default=datetime(year=1900, month=1, day=1))

    fcm_device_token = StringProperty()
    # this property is used to mark users who signed up from internal invitations
    # such as those going through the recruiting pipeline
    # to better mark them in our analytics
    atypical_user = BooleanProperty(default=False)

    def is_global_admin(self):
        # override this function to pass global admin rights off to django
        return self.is_superuser

    @classmethod
    def create(cls, domain, username, password, created_by, created_via, email=None, uuid='', date='',
               user_data=None, by_domain_required_for_log=True, **kwargs):
        web_user = super(WebUser, cls).create(domain, username, password, created_by, created_via, email, uuid,
                                              date, user_data, **kwargs)
        if domain:
            web_user.add_domain_membership(domain, **kwargs)
        web_user.save()
        web_user.log_user_create(domain, created_by, created_via,
                                 by_domain_required_for_log=by_domain_required_for_log)
        return web_user

    def add_domain_membership(self, domain, timezone=None, **kwargs):
        if TABLEAU_USER_SYNCING.enabled(domain):
            from corehq.apps.reports.util import add_tableau_user
            add_tableau_user(domain, self.username)
        super().add_domain_membership(domain, timezone, **kwargs)

    def delete_domain_membership(self, domain, create_record=False):
        if TABLEAU_USER_SYNCING.enabled(domain):
            from corehq.apps.reports.util import delete_tableau_user
            delete_tableau_user(domain, self.username)
        return super().delete_domain_membership(domain, create_record=create_record)

    def is_commcare_user(self):
        return False

    def is_web_user(self):
        return True

    def to_ota_restore_user(self, domain, request_user=None):
        return OTARestoreWebUser(
            domain,
            self,
            request_user=request_user
        )

    def get_owner_ids(self, domain):
        owner_ids = [self.user_id]
        owner_ids.extend(loc.location_id for loc in self._get_case_owning_locations(domain))
        return owner_ids

    @quickcache(['self._id', 'domain'], lambda _: settings.UNIT_TESTING)
    def get_usercase_id(self, domain):
        case = self.get_usercase_by_domain(domain)
        return case.case_id if case else None

    def get_email(self):
        # Do not change the name of this method because this is implementing
        # get_email() from the CommCareMobileContactMixin
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

    def get_domains(self):
        return [dm.domain for dm in self.domain_memberships]

    @classmethod
    def get_admins_by_domain(cls, domain):
        user_ids = cls.ids_by_domain(domain)
        for user_doc in iter_docs(cls.get_db(), user_ids):
            web_user = cls.wrap(user_doc)
            if web_user.is_domain_admin(domain):
                yield web_user

    @classmethod
    def get_billing_admins_by_domain(cls, domain):
        from corehq.apps.users.role_utils import UserRolePresets
        users = cls.by_domain(domain)
        for user in users:
            if user.role_label(domain) == UserRolePresets.BILLING_ADMIN:
                yield user

    @classmethod
    def get_dimagi_emails_by_domain(cls, domain):
        user_ids = cls.ids_by_domain(domain)
        for user_doc in iter_docs(cls.get_db(), user_ids):
            if is_dimagi_email(user_doc['email']):
                yield user_doc['email']

    def save(self, fire_signals=True, **params):
        super().save(fire_signals=fire_signals, **params)
        if fire_signals and not self.to_be_deleted():
            from corehq.apps.callcenter.tasks import sync_web_user_usercases_if_applicable
            for domain in self.get_domains():
                sync_web_user_usercases_if_applicable(self, domain)

    def add_to_assigned_locations(self, domain, location):
        membership = self.get_domain_membership(domain)

        if membership.location_id:
            if location.location_id in membership.assigned_location_ids:
                return
            membership.assigned_location_ids.append(location.location_id)
            self.get_sql_locations.reset_cache(self)
            self.save()
        else:
            self.set_location(domain, location)

    def set_location(self, domain, location_object_or_id):
        # set the primary location for user's domain_membership
        if isinstance(location_object_or_id, str):
            location_id = location_object_or_id
        else:
            location_id = location_object_or_id.location_id

        if not location_id:
            raise AssertionError("You can't set an unsaved location")

        membership = self.get_domain_membership(domain)
        membership.location_id = location_id
        if self.location_id not in membership.assigned_location_ids:
            membership.assigned_location_ids.append(location_id)
            self.get_sql_locations.reset_cache(self)
        self.get_sql_location.reset_cache(self)
        self.save()

    def unset_location(self, domain, fall_back_to_next=False, commit=True):
        """
        Change primary location to next location from assigned_location_ids,
        if there are no more locations in assigned_location_ids, primary location is cleared
        """
        membership = self.get_domain_membership(domain)
        old_location_id = membership.location_id
        if old_location_id:
            membership.assigned_location_ids.remove(old_location_id)
            self.get_sql_locations.reset_cache(self)
        if membership.assigned_location_ids and fall_back_to_next:
            membership.location_id = membership.assigned_location_ids[0]
        else:
            membership.location_id = None
        self.get_sql_location.reset_cache(self)
        if commit:
            self.save()

    def unset_location_by_id(self, domain, location_id, fall_back_to_next=False):
        """
        Unset a location that the user is assigned to that may or may not be primary location
        """
        membership = self.get_domain_membership(domain)
        primary_id = membership.location_id
        if location_id == primary_id:
            # check if primary location
            self.unset_location(domain, fall_back_to_next)
        else:
            membership.assigned_location_ids.remove(location_id)
            self.get_sql_locations.reset_cache(self)
            self.save()

    def reset_locations(self, domain, location_ids, commit=True):
        """
        reset locations to given list of location_ids. Before calling this, primary location
            should be explicitly set/unset via set_location/unset_location
        """
        membership = self.get_domain_membership(domain)
        membership.assigned_location_ids = location_ids
        if not membership.location_id and location_ids:
            membership.location_id = location_ids[0]
        self.get_sql_locations.reset_cache(self)
        if commit:
            self.save()

    @memoized
    def get_sql_location(self, domain):
        from corehq.apps.locations.models import SQLLocation
        loc_id = self.get_location_id(domain)
        if loc_id:
            return SQLLocation.objects.get_or_None(domain=domain, location_id=loc_id)

    def get_location_ids(self, domain):
        return getattr(self.get_domain_membership(domain), 'assigned_location_ids', [])

    @memoized
    def get_sql_locations(self, domain=None):
        from corehq.apps.locations.models import SQLLocation
        loc_ids = self.get_location_ids(domain)
        if loc_ids:
            return SQLLocation.objects.get_locations(loc_ids)
        else:
            return SQLLocation.objects.none()

    def get_location(self, domain):
        return self.get_sql_location(domain)

    def get_usercase_by_domain(self, domain):
        return CommCareCase.objects.get_case_by_external_id(domain, self._id, USERCASE_TYPE)


class FakeUser(WebUser):
    """
    Prevent actually saving user types that don't exist in the database
    """

    def save(self, **kwargs):
        raise NotImplementedError("You aren't allowed to do that!")

    @property
    def _id(self):
        return "fake-user"


class InvalidUser(FakeUser):
    """
    Public users have read-only access to certain domains
    """

    def is_member_of(self, domain_qs):
        return False


class DomainRequest(models.Model):
    '''
    Request to join domain. Requester might or might not already have an account.
    '''
    email = models.CharField(max_length=100, db_index=True)
    full_name = models.CharField(max_length=100, db_index=True)
    is_approved = models.BooleanField(default=False)
    domain = models.CharField(max_length=255, db_index=True)

    class Meta(object):
        app_label = "users"

    @classmethod
    def by_domain(cls, domain, is_approved=False):
        return DomainRequest.objects.filter(domain=domain, is_approved=is_approved)

    @classmethod
    def by_email(cls, domain, email, is_approved=False):
        return DomainRequest.by_domain(domain, is_approved).filter(email=email).first()

    def send_approval_email(self):
        domain_name = Domain.get_by_name(self.domain).display_name()
        params = {
            'domain_name': domain_name,
            'url': absolute_reverse("domain_homepage", args=[self.domain]),
        }
        text_content = render_to_string("users/email/new_domain_request.txt", params)
        html_content = render_to_string("users/email/new_domain_request.html", params)
        subject = _('Request to join %s approved') % domain_name
        send_html_email_async.delay(subject, self.email, html_content, text_content=text_content,
                                    domain=self.domain, use_domain_gateway=True)

    def send_request_email(self):
        domain_name = Domain.get_by_name(self.domain).display_name()
        params = {
            'full_name': self.full_name,
            'email': self.email,
            'domain_name': domain_name,
            'url': absolute_reverse("web_users", args=[self.domain]),
        }
        recipients = {u.get_email() for u in
            WebUser.get_admins_by_domain(self.domain)}
        text_content = render_to_string("users/email/request_domain_access.txt", params)
        html_content = render_to_string("users/email/request_domain_access.html", params)
        subject = _('Request from %(name)s to join %(domain)s') % {
            'name': self.full_name,
            'domain': domain_name,
        }
        send_html_email_async.delay(subject, recipients, html_content, text_content=text_content,
                                    domain=self.domain, use_domain_gateway=True)


class InvitationStatus(object):
    BOUNCED = "Bounced"
    SENT = "Sent"
    DELIVERED = "Delivered"


class Invitation(models.Model):
    EMAIL_ID_PREFIX = "Invitation:"

    uuid = models.UUIDField(primary_key=True, db_index=True, default=uuid4)
    email = models.CharField(max_length=255, db_index=True)
    email_status = models.CharField(max_length=126, null=True)
    invited_by = models.CharField(max_length=126)           # couch id of a WebUser
    invited_on = models.DateTimeField()
    is_accepted = models.BooleanField(default=False)
    domain = models.CharField(max_length=255)
    role = models.CharField(max_length=100, null=True)  # role qualified ID
    program = models.CharField(max_length=126, null=True)   # couch id of a Program
    supply_point = models.CharField(max_length=126, null=True)  # couch id of a Location

    def __repr__(self):
        return f"Invitation(domain='{self.domain}', email='{self.email})"

    @classmethod
    def by_domain(cls, domain, is_accepted=False, **filters):
        return Invitation.objects.filter(domain=domain, is_accepted=is_accepted, **filters)

    @classmethod
    def by_email(cls, email):
        return Invitation.objects.filter(email=email, is_accepted=False)

    @property
    def is_expired(self):
        return self.invited_on.date() + relativedelta(months=1) < datetime.utcnow().date()

    @property
    def email_marked_as_bounced(self):
        return BouncedEmail.get_hard_bounced_emails([self.email])

    def send_activation_email(self, remaining_days=30):
        inviter = CouchUser.get_by_user_id(self.invited_by)
        url = absolute_reverse("domain_accept_invitation", args=[self.domain, self.uuid])
        domain_obj = Domain.get_by_name(self.domain)
        params = {
            "domain": domain_obj.display_name(),
            "url": url,
            "days": remaining_days,
            "inviter": inviter.formatted_name,
            "url_prefix": get_static_url_prefix(),
        }
        from corehq.apps.registration.utils import project_logo_emails_context
        params.update(project_logo_emails_context(domain_obj.name))

        domain_request = DomainRequest.by_email(self.domain, self.email, is_approved=True)
        lang = guess_domain_language(self.domain)
        with override_language(lang):
            if domain_request is None:
                text_content = render_to_string("domain/email/domain_invite.txt", params)
                html_content = render_to_string("domain/email/domain_invite.html", params)
                subject = _('Invitation from %s to join CommCareHQ') % inviter.formatted_name
            else:
                text_content = render_to_string("domain/email/domain_request_approval.txt", params)
                html_content = render_to_string("domain/email/domain_request_approval.html", params)
                subject = _('Request to join CommCareHQ approved')
        send_html_email_async.delay(subject, self.email, html_content,
                                    text_content=text_content,
                                    cc=[inviter.get_email()],
                                    messaging_event_id=f"{self.EMAIL_ID_PREFIX}{self.uuid}",
                                    domain=self.domain,
                                    use_domain_gateway=True)

    def get_role_name(self):
        if self.role:
            if self.role == 'admin':
                return _('Admin')
            else:
                role_id = self.role[len('user-role:'):]
                try:
                    return UserRole.objects.by_couch_id(role_id).name
                except UserRole.DoesNotExist:
                    return _('Unknown Role')
        else:
            return None

    def _send_confirmation_email(self):
        """
        This sends the confirmation email to the invited_by user that their
        invitation was accepted.
        :return:
        """
        invited_user = self.email
        subject = _('{} accepted your invitation to CommCare HQ').format(invited_user)
        recipient = WebUser.get_by_user_id(self.invited_by).get_email()
        context = {
            'invited_user': invited_user,
        }
        html_content = render_to_string('domain/email/invite_confirmation.html',
                                        context)
        text_content = render_to_string('domain/email/invite_confirmation.txt',
                                        context)
        send_html_email_async.delay(
            subject,
            recipient,
            html_content,
            text_content=text_content,
            domain=self.domain,
            use_domain_gateway=True
        )

    def accept_invitation_and_join_domain(self, web_user):
        """
        Call this method to confirm that a user has accepted the invite to
        a domain and add them as a member to the domain in the invitation.
        :param web_user: WebUser
        """
        web_user.add_as_web_user(
            self.domain,
            role=self.role,
            location_id=self.supply_point,
            program_id=self.program,
        )
        self.is_accepted = True
        self.save()
        self._send_confirmation_email()


class DomainRemovalRecord(DeleteRecord):
    user_id = StringProperty()
    domain_membership = SchemaProperty(DomainMembership)

    def undo(self):
        user = WebUser.get_by_user_id(self.user_id)
        user.domain_memberships.append(self.domain_membership)
        user.domains.append(self.domain)
        user.save()
        DeletedCouchDoc.objects.filter(
            doc_id=self._id,
            doc_type=self.doc_type,
        ).delete()
        if TABLEAU_USER_SYNCING.enabled(self.domain):
            from corehq.apps.reports.util import add_tableau_user
            add_tableau_user(self.domain, user.username)


class UserReportingMetadataStaging(models.Model):
    id = models.BigAutoField(primary_key=True)
    domain = models.TextField()
    user_id = models.TextField()
    app_id = models.TextField(null=True)  # not all form submissions include an app_id
    modified_on = models.DateTimeField(auto_now=True)
    created_on = models.DateTimeField(auto_now=True)

    # should build_id actually be nullable?
    build_id = models.TextField(null=True)

    # The following properties are null if a user has not submitted a form since their last sync
    xform_version = models.IntegerField(null=True)
    form_meta = models.JSONField(null=True)  # This could be filtered to only the parts we need
    received_on = models.DateTimeField(null=True)

    # The following properties are null if a user has not synced since their last form submission
    device_id = models.TextField(null=True)
    sync_date = models.DateTimeField(null=True)

    # The following properties are set when a mobile heartbeat occurs
    app_version = models.IntegerField(null=True)
    num_unsent_forms = models.IntegerField(null=True)
    num_quarantined_forms = models.IntegerField(null=True)
    commcare_version = models.TextField(null=True)
    build_profile_id = models.TextField(null=True)
    last_heartbeat = models.DateTimeField(null=True)
    fcm_token = models.TextField(null=True)

    @classmethod
    def add_submission(cls, domain, user_id, app_id, build_id, version, metadata, received_on):
        params = {
            'domain': domain,
            'user_id': user_id,
            'app_id': app_id,
            'build_id': build_id,
            'xform_version': version,
            'form_meta': json.dumps(metadata),
            'received_on': received_on,
        }
        with connection.cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {cls._meta.db_table} AS staging (
                    domain, user_id, app_id, modified_on, created_on,
                    build_id,
                    xform_version, form_meta, received_on
                ) VALUES (
                    %(domain)s, %(user_id)s, %(app_id)s, CLOCK_TIMESTAMP(), CLOCK_TIMESTAMP(),
                    %(build_id)s,
                    %(xform_version)s, %(form_meta)s, %(received_on)s
                )
                ON CONFLICT (domain, user_id, app_id)
                DO UPDATE SET
                    modified_on = CLOCK_TIMESTAMP(),
                    build_id = EXCLUDED.build_id,
                    xform_version = EXCLUDED.xform_version,
                    form_meta = EXCLUDED.form_meta,
                    received_on = EXCLUDED.received_on
                WHERE staging.received_on IS NULL OR EXCLUDED.received_on > staging.received_on
                """, params)

    @classmethod
    def add_sync(cls, domain, user_id, app_id, build_id, sync_date, device_id):
        params = {
            'domain': domain,
            'user_id': user_id,
            'app_id': app_id,
            'build_id': build_id,
            'sync_date': sync_date,
            'device_id': device_id,
        }
        with connection.cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {cls._meta.db_table} AS staging (
                    domain, user_id, app_id, modified_on, created_on,
                    build_id,
                    sync_date, device_id
                ) VALUES (
                    %(domain)s, %(user_id)s, %(app_id)s, CLOCK_TIMESTAMP(), CLOCK_TIMESTAMP(),
                    %(build_id)s,
                    %(sync_date)s, %(device_id)s
                )
                ON CONFLICT (domain, user_id, app_id)
                DO UPDATE SET
                    modified_on = CLOCK_TIMESTAMP(),
                    build_id = EXCLUDED.build_id,
                    sync_date = EXCLUDED.sync_date,
                    device_id = EXCLUDED.device_id
                WHERE staging.sync_date IS NULL OR EXCLUDED.sync_date > staging.sync_date
                """, params)

    @classmethod
    def add_heartbeat(cls, domain, user_id, app_id, build_id, sync_date, device_id,
                      app_version, num_unsent_forms, num_quarantined_forms,
                      commcare_version, build_profile_id, fcm_token):
        params = {
            'domain': domain,
            'user_id': user_id,
            'app_id': app_id,
            'build_id': build_id,
            'sync_date': sync_date,
            'device_id': device_id,
            'app_version': app_version,
            'num_unsent_forms': num_unsent_forms,
            'num_quarantined_forms': num_quarantined_forms,
            'commcare_version': commcare_version,
            'build_profile_id': build_profile_id,
            'fcm_token': fcm_token
        }
        with connection.cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {cls._meta.db_table} AS staging (
                    domain, user_id, app_id, modified_on, created_on,
                    build_id,
                    sync_date, device_id,
                    app_version, num_unsent_forms, num_quarantined_forms,
                    commcare_version, build_profile_id, last_heartbeat, fcm_token
                ) VALUES (
                    %(domain)s, %(user_id)s, %(app_id)s, CLOCK_TIMESTAMP(), CLOCK_TIMESTAMP(),
                    %(build_id)s,
                    %(sync_date)s, %(device_id)s,
                    %(app_version)s, %(num_unsent_forms)s, %(num_quarantined_forms)s,
                    %(commcare_version)s, %(build_profile_id)s, CLOCK_TIMESTAMP(), %(fcm_token)s
                )
                ON CONFLICT (domain, user_id, app_id)
                DO UPDATE SET
                    modified_on = CLOCK_TIMESTAMP(),
                    build_id = COALESCE(EXCLUDED.build_id, staging.build_id),
                    sync_date = COALESCE(EXCLUDED.sync_date, staging.sync_date),
                    device_id = COALESCE(EXCLUDED.device_id, staging.device_id),
                    app_version = EXCLUDED.app_version,
                    num_unsent_forms = EXCLUDED.num_unsent_forms,
                    num_quarantined_forms = EXCLUDED.num_quarantined_forms,
                    commcare_version = EXCLUDED.commcare_version,
                    build_profile_id = EXCLUDED.build_profile_id,
                    last_heartbeat = CLOCK_TIMESTAMP(),
                    fcm_token = EXCLUDED.fcm_token
                WHERE staging.last_heartbeat is NULL or EXCLUDED.last_heartbeat > staging.last_heartbeat
                """, params)

    def process_record(self, user):
        from corehq.pillows.synclog import mark_last_synclog
        from pillowtop.processors.form import mark_latest_submission

        save = False
        if not user or user.is_deleted():
            return

        if self.received_on:
            save = mark_latest_submission(
                self.domain, user, self.app_id, self.build_id,
                self.xform_version, self.form_meta, self.received_on, save_user=False
            )
        if self.device_id or self.sync_date or self.last_heartbeat:
            device_app_meta = DeviceAppMeta(
                app_id=self.app_id,
                build_id=self.build_id,
                build_version=self.app_version,
                last_heartbeat=self.last_heartbeat,
                last_sync=self.sync_date,
                num_unsent_forms=self.num_unsent_forms,
                num_quarantined_forms=self.num_quarantined_forms
            )
            if not self.last_heartbeat:
                # coming from sync
                latest_build_date = self.sync_date
            else:
                # coming from hearbeat
                latest_build_date = self.modified_on
            save |= mark_last_synclog(
                self.domain, user, self.app_id, self.build_id,
                self.sync_date, latest_build_date, self.device_id, device_app_meta,
                commcare_version=self.commcare_version, build_profile_id=self.build_profile_id,
                fcm_token=self.fcm_token, fcm_token_timestamp=self.last_heartbeat, save_user=False
            )
        if save:
            # update_django_user=False below is an optimization that allows us to update the CouchUser
            # without propagating that change to SQL.
            # This is an optimization we're able to do safely only because we happen to know that
            # the present workflow only updates properties that are *not* stored on the django (SQL) user model.
            # We have seen that these frequent updates to the SQL user table
            # occasionally create deadlocks or pile-ups,
            # which can be avoided by omitting that extraneous write entirely.
            user.save(fire_signals=False, update_django_user=False)

    class Meta(object):
        unique_together = ('domain', 'user_id', 'app_id')


class ApiKeyManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset()\
            .filter(is_active=True)\
            .exclude(expiration_date__lt=datetime.now())


class HQApiKey(models.Model):
    user = models.ForeignKey(User, related_name='api_keys', on_delete=models.CASCADE)
    key = models.CharField(max_length=128, blank=True, default='', db_index=True)
    name = models.CharField(max_length=255, blank=True, default='')
    created = models.DateTimeField(default=timezone.now)
    ip_allowlist = ArrayField(models.GenericIPAddressField(), default=list)
    domain = models.CharField(max_length=255, blank=True, default='')
    role_id = models.CharField(max_length=40, blank=True, default='')
    is_active = models.BooleanField(default=True)
    deactivated_on = models.DateTimeField(blank=True, null=True)
    expiration_date = models.DateTimeField(blank=True, null=True)
    # Not update with every request. Can be a couple of seconds out of date
    last_used = models.DateTimeField(blank=True, null=True)

    objects = ApiKeyManager()
    all_objects = models.Manager()

    class Meta(object):
        unique_together = ('user', 'name')

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()

        return super().save(*args, **kwargs)

    def generate_key(self):
        # From tastypie
        new_uuid = uuid4()
        return hmac.new(new_uuid.bytes, digestmod=sha1).hexdigest()

    @property
    @memoized
    def role(self):
        if self.role_id:
            try:
                return UserRole.objects.by_couch_id(self.role_id)
            except UserRole.DoesNotExist:
                logging.exception('no role with id %s found in domain %s' % (self.role_id, self.domain))
        elif self.domain:
            return CouchUser.from_django_user(self.user).get_domain_membership(self.domain).role
        return None


class UserHistory(models.Model):
    """
    HQ Adaptation of Django's LogEntry model
    """
    CREATE = 1
    UPDATE = 2
    DELETE = 3
    CLEAR = 4  # currently only for logging purposes

    ACTION_CHOICES = (
        (CREATE, _('Create')),
        (UPDATE, _('Update')),
        (DELETE, _('Delete')),
    )
    by_domain = models.CharField(max_length=255, null=True)
    for_domain = models.CharField(max_length=255, null=True)
    user_type = models.CharField(max_length=255)  # CommCareUser / WebUser
    user_repr = models.CharField(max_length=255, null=True)
    user_id = models.CharField(max_length=128)
    changed_by_repr = models.CharField(max_length=255, null=True)
    changed_by = models.CharField(max_length=128)
    # ToDo: remove post migration/reset of existing records
    message = models.TextField(blank=True, null=True)
    # JSON structured replacement for the deprecated text message field
    change_messages = models.JSONField(default=dict)
    changed_at = models.DateTimeField(auto_now_add=True, editable=False)
    action = models.PositiveSmallIntegerField(choices=ACTION_CHOICES)
    user_upload_record = models.ForeignKey(UserUploadRecord, null=True, on_delete=models.SET_NULL)
    # ToDo: remove post migration/reset of existing records
    """
    dict with keys:
       changed_via: one of the USER_CHANGE_VIA_* constants
       changes: a dict of CouchUser attributes that changed and their new values
    """
    details = models.JSONField(default=dict)
    # ToDo: remove blank=true post migration/reset of existing records since it will always be present
    # same as the deprecated details.changed_via
    # one of the USER_CHANGE_VIA_* constants
    changed_via = models.CharField(max_length=255, blank=True)
    # same as the deprecated details.changes
    # a dict of CouchUser attributes that changed and their new values
    changes = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        indexes = [
            models.Index(fields=['by_domain']),
            models.Index(fields=['for_domain']),
        ]


class DeactivateMobileWorkerTriggerUpdateMessage:
    UPDATED = 'updated'
    CREATED = 'created'
    DELETED = 'deleted'


class DeactivateMobileWorkerTrigger(models.Model):
    """
    This determines if a Mobile Worker / CommCareUser is to be deactivated
    after a certain date.
    """
    domain = models.CharField(max_length=255)
    user_id = models.CharField(max_length=255)
    deactivate_after = models.DateField()

    @classmethod
    def deactivate_mobile_workers(cls, domain, date_deactivation):
        """
        This deactivates all CommCareUsers who have a matching
        DeactivateMobileWorkerTrigger with deactivate_after
        :param domain: String - domain name
        :param date_deactivation: Date
        """
        trigger_query = cls.objects.filter(
            domain=domain,
            deactivate_after__lte=date_deactivation
        )
        user_ids = trigger_query.values_list('user_id', flat=True)
        for chunked_ids in chunked(user_ids, 100):
            bulk_auto_deactivate_commcare_users(chunked_ids, domain)
            cls.objects.filter(domain=domain, user_id__in=chunked_ids).delete()

    @classmethod
    def update_trigger(cls, domain, user_id, deactivate_after):
        existing_trigger = cls.objects.filter(domain=domain, user_id=user_id)
        if not deactivate_after:
            if existing_trigger.exists():
                existing_trigger.delete()
                return DeactivateMobileWorkerTriggerUpdateMessage.DELETED
            # noop
            return
        if isinstance(deactivate_after, str):
            try:
                deactivate_after = get_date_from_month_and_year_string(deactivate_after)
            except ValueError:
                raise ValueError("Deactivate After Date is not in MM-YYYY format")
        if isinstance(deactivate_after, date):
            if existing_trigger.exists():
                trigger = existing_trigger.first()
                if trigger.deactivate_after == deactivate_after:
                    # don't update or record a message
                    return
                trigger.deactivate_after = deactivate_after
                trigger.save()
                return DeactivateMobileWorkerTriggerUpdateMessage.UPDATED
            else:
                cls.objects.create(
                    domain=domain,
                    user_id=user_id,
                    deactivate_after=deactivate_after,
                )
                return DeactivateMobileWorkerTriggerUpdateMessage.CREATED

    @classmethod
    def get_deactivate_after_date(cls, domain, user_id):
        existing_trigger = cls.objects.filter(domain=domain, user_id=user_id)
        if not existing_trigger.exists():
            return None
        return existing_trigger.first().deactivate_after


def check_and_send_limit_email(domain, plan_limit, user_count, prev_count):
    ADDITIONAL_USERS_PRICING = ("https://confluence.dimagi.com/display/commcarepublic"
                                "/CommCare+Pricing+FAQs#CommCarePricingFAQs-Feesforadditionalusers")
    ENTERPRISE_LIMIT = -1
    if plan_limit == ENTERPRISE_LIMIT:
        return

    WARNING_PERCENT = 0.9
    if user_count >= plan_limit > prev_count:
        at_capacity = True
    elif plan_limit > user_count >= (WARNING_PERCENT * plan_limit) > prev_count:
        at_capacity = False
    else:
        return

    billing_admins = [admin.username for admin in WebUser.get_billing_admins_by_domain(domain)]
    admins = [admin.username for admin in WebUser.get_admins_by_domain(domain)]

    if at_capacity:
        subject = _("User count has reached the Plan limit for {}").format(domain)
    else:
        subject = _("User count has reached 90% of the Plan limit for {}").format(domain)
    send_html_email_async(
        subject,
        set(admins + billing_admins),
        render_to_string('users/email/user_limit_notice.html', context={
            'at_capacity': at_capacity,
            'url': ADDITIONAL_USERS_PRICING,
            'user_count': user_count,
            'plan_limit': plan_limit,
        }),
        domain=domain,
        use_domain_gateway=True,
    )
    return


class ConnectIDUserLink(models.Model):
    connectid_username = models.TextField()
    commcare_user = models.ForeignKey(User, related_name='connectid_user', on_delete=models.CASCADE)
    domain = models.TextField()

    class Meta:
        unique_together = ('domain', 'commcare_user')
