import json
import logging
import re
from datetime import datetime, timedelta
from uuid import uuid4
from xml.etree import cElementTree as ElementTree

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.postgres.fields import JSONField
from django.db import connection, models, router
from django.template.loader import render_to_string
from django.utils.translation import override as override_language
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from couchdbkit import MultipleResultsFound, ResourceNotFound
from couchdbkit.exceptions import BadValueError, ResourceConflict
from dateutil.relativedelta import relativedelta
from memoized import memoized

from casexml.apps.case.mock import CaseBlock
from casexml.apps.phone.models import OTARestoreCommCareUser, OTARestoreWebUser
from casexml.apps.phone.restore_caching import get_loadtest_factor_for_user
from corehq.apps.users.exceptions import IllegalAccountConfirmation
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
from dimagi.utils.couch.migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin
from dimagi.utils.couch.undo import DELETED_SUFFIX, DeleteRecord
from dimagi.utils.dates import force_to_datetime
from dimagi.utils.logging import log_signal_errors, notify_exception
from dimagi.utils.modules import to_function
from dimagi.utils.web import get_static_url_prefix

from corehq import toggles
from corehq.apps.app_manager.const import USERCASE_TYPE
from corehq.apps.cachehq.mixins import QuickCachedDocumentMixin
from corehq.apps.commtrack.const import USER_LOCATION_OWNER_MAP_TYPE
from corehq.apps.domain.models import Domain, LicenseAgreement
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.domain.utils import (
    domain_restricts_superusers,
    guess_domain_language,
    normalize_domain_name,
)
from corehq.apps.hqwebapp.tasks import send_html_email_async
from corehq.apps.sms.mixin import CommCareMobileContactMixin, apply_leniency
from corehq.apps.users.landing_pages import ALL_LANDING_PAGES
from corehq.apps.users.permissions import EXPORT_PERMISSIONS
from corehq.apps.users.tasks import (
    tag_cases_as_deleted_and_remove_indices,
    tag_forms_as_deleted_rebuild_associated_cases,
    tag_system_forms_as_deleted,
    undelete_system_forms,
)
from corehq.apps.users.util import (
    filter_by_app,
    user_display_string,
    user_location_data,
    username_to_user_id,
)
from corehq.form_processor.exceptions import CaseNotFound, NotAllowed
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.util.dates import get_timestamp
from corehq.util.quickcache import quickcache
from corehq.util.view_utils import absolute_reverse

COUCH_USER_AUTOCREATED_STATUS = 'autocreated'

MAX_LOGIN_ATTEMPTS = 5


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


class Permissions(DocumentSchema):
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

    edit_motech = BooleanProperty(default=False)
    edit_data = BooleanProperty(default=False)
    edit_apps = BooleanProperty(default=False)
    edit_shared_exports = BooleanProperty(default=False)
    access_all_locations = BooleanProperty(default=True)

    view_reports = BooleanProperty(default=False)
    view_report_list = StringListProperty(default=[])

    edit_billing = BooleanProperty(default=False)
    report_an_issue = BooleanProperty(default=True)

    view_web_apps = BooleanProperty(default=True)
    view_web_apps_list = StringListProperty(default=[])

    view_file_dropzone = BooleanProperty(default=False)
    manage_releases = BooleanProperty(default=True)
    manage_releases_list = StringListProperty(default=[])

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

    def view_web_app(self, app):
        if self.view_web_apps:
            return True
        return any(app_id in self.view_web_apps_list for app_id in [app['_id'], app['copy_of']])

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
            view_web_users=True,
            view_roles=True,
            edit_commcare_users=True,
            view_commcare_users=True,
            edit_groups=True,
            view_groups=True,
            edit_users_in_groups=True,
            edit_locations=True,
            view_locations=True,
            edit_users_in_locations=True,
            edit_motech=True,
            edit_data=True,
            edit_apps=True,
            view_reports=True,
            edit_billing=True,
            edit_shared_exports=True,
            view_file_dropzone=True,
        )


class UserRolePresets(object):
    # this is kind of messy, but we're only marking for translation (and not using ugettext_lazy)
    # because these are in JSON and cannot be serialized
    # todo: apply translation to these in the UI
    # note: these are also tricky to change because these are just some default names,
    # that end up being stored in the database. Think about the consequences of changing these before you do.
    READ_ONLY_NO_REPORTS = ugettext_noop("Read Only (No Reports)")
    APP_EDITOR = ugettext_noop("App Editor")
    READ_ONLY = ugettext_noop("Read Only")
    FIELD_IMPLEMENTER = ugettext_noop("Field Implementer")
    BILLING_ADMIN = ugettext_noop("Billing Admin")
    INITIAL_ROLES = (
        READ_ONLY,
        APP_EDITOR,
        FIELD_IMPLEMENTER,
        BILLING_ADMIN
    )

    @classmethod
    def get_preset_map(cls):
        return {
            cls.READ_ONLY_NO_REPORTS: lambda: Permissions(),
            cls.READ_ONLY: lambda: Permissions(view_reports=True),
            cls.FIELD_IMPLEMENTER: lambda: Permissions(edit_commcare_users=True,
                                                       view_commcare_users=True,
                                                       edit_groups=True,
                                                       view_groups=True,
                                                       edit_locations=True,
                                                       view_locations=True,
                                                       edit_shared_exports=True,
                                                       view_reports=True),
            cls.APP_EDITOR: lambda: Permissions(edit_apps=True, view_reports=True),
            cls.BILLING_ADMIN: lambda: Permissions(edit_billing=True)
        }

    @classmethod
    def get_permissions(cls, preset):
        preset_map = cls.get_preset_map()
        if preset not in preset_map:
            return None
        return preset_map[preset]()


class UserRole(QuickCachedDocumentMixin, Document):
    domain = StringProperty()
    name = StringProperty()
    default_landing_page = StringProperty(
        choices=[page.id for page in ALL_LANDING_PAGES],
    )
    permissions = SchemaProperty(Permissions)
    is_non_admin_editable = BooleanProperty(default=False)
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
        return [x for x in all_roles if x.is_archived == is_archived]

    @classmethod
    def by_domain_and_name(cls, domain, name, is_archived=False):
        # todo change this view to show is_archived status or move to PRBAC UserRole
        all_roles = cls.view(
            'users/roles_by_domain',
            key=[domain, name],
            include_docs=True,
            reduce=False,
        )
        return [x for x in all_roles if x.is_archived == is_archived]

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
            preset_match = [x for x in UserRolePresets.get_preset_map().items() if x[1]() == permissions]
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
        return [x for x in cls.by_domain(domain) if x.name not in UserRolePresets.INITIAL_ROLES]

    @classmethod
    def reset_initial_roles_for_domain(cls, domain):
        initial_roles = [x for x in cls.by_domain(domain) if x.name in UserRolePresets.INITIAL_ROLES]
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

    @classmethod
    def get_preset_permission_by_name(cls, name):
        matches = {k for k, v in PERMISSIONS_PRESETS.items() if v['name'] == name}
        return matches.pop() if matches else None

    @classmethod
    def preset_and_domain_role_names(cls, domain_name):
        return cls.preset_permissions_names().union(set([role.name for role in cls.by_domain(domain_name)]))

    @classmethod
    def preset_permissions_names(cls):
        return {details['name'] for role, details in PERMISSIONS_PRESETS.items()}


PERMISSIONS_PRESETS = {
    'edit-apps': {
        'name': 'App Editor',
        'permissions': Permissions(
            edit_apps=True,
            view_reports=True,
        ),
    },
    'field-implementer': {
        'name': 'Field Implementer',
        'permissions': Permissions(
            edit_commcare_users=True,
            view_commcare_users=True,
            edit_groups=True,
            view_groups=True,
            edit_locations=True,
            view_locations=True,
            edit_shared_exports=True,
            view_reports=True,
        ),
    },
    'read-only': {
        'name': 'Read Only',
        'permissions': Permissions(
            view_reports=True,
        ),
    },
    'no-permissions': {
        'name': 'Read Only',
        'permissions': Permissions(
            view_reports=True,
        ),
    },
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
            return Permissions()

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

    class Meta(object):
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
    def has_permission(self, domain, permission, data=None, restrict_global_admin=False):
        if not restrict_global_admin:
            # is_admin is the same as having all the permissions set
            if self.is_global_admin() and (domain is None or not domain_restricts_superusers(domain)):
                return True
            elif self.is_domain_admin(domain):
                return True

        dm = self.get_domain_membership(domain)
        if dm:
            # an admin has access to all features by default, restrict that if needed
            if dm.is_admin and restrict_global_admin:
                return False
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
        if self.is_member_of(domain):
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
            dm.role_id = None
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
            return _("Unknown User")
        except DomainMembershipError:
            return _("Dimagi User") if self.is_global_admin() else _("Unauthorized User")
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
    CURRENT_VERSION = '3.0'  # Set this to the most up to date version of the eula
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

        for key, prop in self.properties().items():
            new_val = getattr(other, key)
            if new_val:
                old_val = getattr(self, key)
                if not old_val:
                    setattr(self, key, new_val)
                    continue

                prop_is_date = isinstance(prop, DateTimeProperty)
                if prop_is_date and new_val > old_val:
                    setattr(self, key, new_val)
                elif not prop_is_date and old_val != new_val:
                    setattr(self, key, new_val)

        self._update_latest_request()


class DeviceIdLastUsed(DocumentSchema):
    device_id = StringProperty()
    last_used = DateTimeProperty()
    commcare_version = StringProperty()
    app_meta = SchemaListProperty(DeviceAppMeta)

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
    user_data = DictProperty()
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
        return self.username.endswith('@dimagi.com')

    def is_locked_out(self):
        return self.login_attempts >= MAX_LOGIN_ATTEMPTS

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

    def __str__(self):
        return "<%s '%s'>" % (self.__class__.__name__, self.get_id)

    def get_email(self):
        # Do not change the name of this method because this ends up implementing
        # get_email() from the CommCareMobileContactMixin for the CommCareUser
        return self.email

    def is_commcare_user(self):
        return self._get_user_type() == 'commcare'

    def is_web_user(self):
        return self._get_user_type() == 'web'

    def supports_lockout(self):
        return self.is_web_user() or toggles.MOBILE_LOGIN_LOCKOUT.enabled(self.domain)

    def _get_user_type(self):
        if self.doc_type == 'WebUser':
            return 'web'
        elif self.doc_type == 'CommCareUser':
            return 'commcare'
        else:
            raise NotImplementedError(f'Unrecognized user type {self.doc_type!r}')

    @property
    def projects(self):
        return list(map(Domain.get_by_name, self.get_domains()))

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

    @property
    def user_session_data(self):
        from corehq.apps.custom_data_fields.models import (
            SYSTEM_PREFIX,
            COMMCARE_USER_TYPE_KEY,
            COMMCARE_USER_TYPE_DEMO
        )

        session_data = self.to_json().get('user_data')

        if self.is_commcare_user() and self.is_demo_user:
            session_data.update({
                COMMCARE_USER_TYPE_KEY: COMMCARE_USER_TYPE_DEMO
            })

        session_data.update({
            '{}_first_name'.format(SYSTEM_PREFIX): self.first_name,
            '{}_last_name'.format(SYSTEM_PREFIX): self.last_name,
            '{}_phone_number'.format(SYSTEM_PREFIX): self.phone_number,
        })
        return session_data

    def delete(self):
        self.clear_quickcache_for_user()
        try:
            user = self.get_django_user()
            user.delete()
        except User.DoesNotExist:
            pass
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
        return queryset.get(username__iexact=self.username)

    def add_phone_number(self, phone_number, default=False, **kwargs):
        """ Don't add phone numbers if they already exist """
        if not isinstance(phone_number, str):
            phone_number = str(phone_number)
        self.phone_numbers = _add_to_list(self.phone_numbers, phone_number, default)

    def set_default_phone_number(self, phone_number):
        self.add_phone_number(phone_number, True)
        self.save()

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
                bool(re.compile(settings.PREVIEWER_RE).match(self.username)))

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
        from corehq.apps.hqwebapp.templatetags.hq_shared_tags import _get_domain_list
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
        _get_domain_list.clear(self)

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

        user_data = {'commcare_project': domain}
        user_data.update(kwargs.get('user_data', {}))
        couch_user.user_data = user_data
        couch_user.sync_from_django_user(django_user)
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

    def save(self, fire_signals=True, **params):
        self.last_modified = datetime.utcnow()
        self.clear_quickcache_for_user()
        with CriticalSection(['username-check-%s' % self.username], timeout=120):
            # test no username conflict
            by_username = self.get_db().view('users/by_username', key=self.username, reduce=False).first()
            if by_username and by_username['id'] != self._id:
                raise self.Inconsistent("CouchUser with username %s already exists" % self.username)

            if self._rev and not self.to_be_deleted():
                django_user = self.sync_to_django_user()
                django_user.save()

            super(CouchUser, self).save(**params)

        if fire_signals:
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
        try:
            domain = domain or self.current_domain
        except AttributeError:
            domain = None

        if self.is_commcare_user():
            role = self.get_role(domain)
            if role is None:
                return []
            else:
                return role.permissions.view_report_list
        else:
            dm = self.get_domain_membership(domain)
            return dm.viewable_reports() if dm else []

    def can_view_some_reports(self, domain):
        return self.can_view_reports(domain) or bool(self.get_viewable_reports(domain))

    def can_access_any_exports(self, domain=None):
        return self.can_view_reports(domain) or any([
            permission_slug for permission_slug in self._get_viewable_report_slugs(domain)
            if permission_slug in EXPORT_PERMISSIONS
        ])

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
            try:
                domain = domain or self.current_domain
            except AttributeError:
                domain = None
            return self.has_permission(domain, perm, data)
        return fn

    def get_location_id(self, domain):
        return getattr(self.get_domain_membership(domain), 'location_id', None)

    def set_has_built_app(self):
        if not self.has_built_app:
            self.has_built_app = True
            self.save()


class CommCareUser(CouchUser, SingleMembershipMixin, CommCareMobileContactMixin):

    domain = StringProperty()
    registering_device_id = StringProperty()
    # used by loadtesting framework - should typically be empty
    loadtest_factor = IntegerProperty()
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
        if not data.get('user_data', {}).get('commcare_project'):
            data['user_data'] = dict(data['user_data'], **{'commcare_project': data['domain']})

        # Todo; remove after migration
        from corehq.apps.users.management.commands import add_multi_location_property
        add_multi_location_property.Command().migrate_user(data)

        return super(CommCareUser, cls).wrap(data)

    def _is_demo_user_cached_value_is_stale(self):
        from corehq.apps.users.dbaccessors.all_commcare_users import get_practice_mode_mobile_workers
        cached_demo_users = get_practice_mode_mobile_workers.get_cached_value(self.domain)
        if cached_demo_users is not Ellipsis:
            cached_is_demo_user = any(user['_id'] == self._id for user in cached_demo_users)
            if cached_is_demo_user != self.is_demo_user:
                return True
        return False

    def clear_quickcache_for_user(self):
        from corehq.apps.users.dbaccessors.all_commcare_users import get_practice_mode_mobile_workers
        self.get_usercase_id.clear(self)
        get_loadtest_factor_for_user.clear(self.domain, self.user_id)

        if self._is_demo_user_cached_value_is_stale():
            get_practice_mode_mobile_workers.clear(self.domain)
        super(CommCareUser, self).clear_quickcache_for_user()

    def save(self, fire_signals=True, spawn_task=False, **params):
        is_new_user = self.new_document  # before saving, check if this is a new document
        super(CommCareUser, self).save(fire_signals=fire_signals, **params)

        if fire_signals:
            from corehq.apps.callcenter.tasks import sync_user_cases_if_applicable
            from .signals import commcare_user_post_save
            results = commcare_user_post_save.send_robust(sender='couch_user', couch_user=self,
                                                          is_new_user=is_new_user)
            log_signal_errors(results, "Error occurred while syncing user (%s)", {'username': self.username})
            sync_user_cases_if_applicable(self, spawn_task)

    def delete(self):
        from corehq.apps.ota.utils import delete_demo_restore_for_user
        # clear demo restore objects if any
        delete_demo_restore_for_user(self)

        super(CommCareUser, self).delete()

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
    def create(cls,
               domain,
               username,
               password,
               email=None,
               uuid='',
               date='',
               phone_number=None,
               location=None,
               commit=True,
               is_account_confirmed=True,
               **kwargs):
        """
        Main entry point into creating a CommCareUser (mobile worker).
        """
        uuid = uuid or uuid4().hex
        # if the account is not confirmed, also set is_active false so they can't login
        if 'is_active' not in kwargs:
            kwargs['is_active'] = is_account_confirmed
        elif not is_account_confirmed:
            assert not kwargs['is_active'], \
                "it's illegal to create a user with is_active=True and is_account_confirmed=False"
        commcare_user = super(CommCareUser, cls).create(domain, username, password, email, uuid, date, **kwargs)
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

        return commcare_user

    @property
    def filter_flag(self):
        from corehq.apps.reports.models import HQUserType
        return HQUserType.ACTIVE

    @property
    def project(self):
        return Domain.get_by_name(self.domain)

    def is_commcare_user(self):
        return True

    def is_web_user(self):
        return False

    def to_ota_restore_user(self):
        return OTARestoreCommCareUser(
            self.domain,
            self,
            loadtest_factor=self.loadtest_factor or 1,
        )

    def _get_form_ids(self):
        return FormAccessors(self.domain).get_form_ids_for_user(self.user_id)

    def _get_case_ids(self):
        return CaseAccessors(self.domain).get_case_ids_by_owners([self.user_id])

    def _get_deleted_form_ids(self):
        return FormAccessors(self.domain).get_deleted_form_ids_for_user(self.user_id)

    def _get_deleted_case_ids(self):
        return CaseAccessors(self.domain).get_deleted_case_ids_by_owner(self.user_id)

    def get_owner_ids(self, domain=None):
        owner_ids = [self.user_id]
        owner_ids.extend([g._id for g in self.get_case_sharing_groups()])
        return owner_ids

    def unretire(self):
        """
        This un-deletes a user, but does not fully restore the state to
        how it previously was. Using this has these caveats:
        - It will not restore Case Indexes that were removed
        - It will not restore the user's phone numbers
        - It will not restore reminders for cases
        """
        NotAllowed.check(self.domain)
        by_username = self.get_db().view('users/by_username', key=self.username, reduce=False).first()
        if by_username and by_username['id'] != self._id:
            return False, "A user with the same username already exists in the system"
        if self.base_doc.endswith(DELETED_SUFFIX):
            self.base_doc = self.base_doc[:-len(DELETED_SUFFIX)]

        deleted_form_ids = self._get_deleted_form_ids()
        FormAccessors(self.domain).soft_undelete_forms(deleted_form_ids)

        deleted_case_ids = self._get_deleted_case_ids()
        CaseAccessors(self.domain).soft_undelete_cases(deleted_case_ids)

        undelete_system_forms.delay(self.domain, set(deleted_form_ids), set(deleted_case_ids))
        self.save()
        return True, None

    def retire(self):
        NotAllowed.check(self.domain)
        suffix = DELETED_SUFFIX
        deletion_id = uuid4().hex
        deletion_date = datetime.utcnow()
        # doc_type remains the same, since the views use base_doc instead
        if not self.base_doc.endswith(suffix):
            self.base_doc += suffix
            self['-deletion_id'] = deletion_id
            self['-deletion_date'] = deletion_date

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

        try:
            django_user = self.get_django_user()
        except User.DoesNotExist:
            pass
        else:
            django_user.delete()
        self.save()

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
        from corehq.apps.locations.models import get_case_sharing_groups_for_locations
        # get faked location group objects
        groups = list(get_case_sharing_groups_for_locations(
            self.get_sql_locations(self.domain),
            self._id
        ))

        groups += [group for group in Group.by_user_id(self._id) if group.case_sharing]
        return groups

    def get_reporting_groups(self):
        from corehq.apps.groups.models import Group
        return [group for group in Group.by_user_id(self._id) if group.reporting]

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
        return Group.by_user_id(self._id, wrap=False)

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
            group.remove_user(self._id)
            touched.append(group)

        Group.bulk_save(touched)

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
            self.user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
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
        from corehq.apps.fixtures.models import UserFixtureType

        if not location.location_id:
            raise AssertionError("You can't set an unsaved location")

        self.user_data['commcare_location_id'] = location.location_id

        if not location.location_type_object.administrative:
            # just need to trigger a get or create to make sure
            # this exists, otherwise things blow up
            sp = SupplyInterface(self.domain).get_or_create_by_location(location)

            self.user_data.update({
                'commtrack-supply-point': sp.case_id
            })

        self.create_location_delegates([location])

        self.user_data.update({
            'commcare_primary_case_sharing_id':
            location.group_id
        })

        self.update_fixture_status(UserFixtureType.LOCATION)
        self.location_id = location.location_id
        self.get_domain_membership(self.domain).location_id = location.location_id
        if self.location_id not in self.assigned_location_ids:
            self.assigned_location_ids.append(self.location_id)
            self.get_domain_membership(self.domain).assigned_location_ids.append(self.location_id)
            self.user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
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
        from corehq.apps.fixtures.models import UserFixtureType
        from corehq.apps.locations.models import SQLLocation
        old_primary_location_id = self.location_id
        if old_primary_location_id:
            self._remove_location_from_user(old_primary_location_id)

        if self.assigned_location_ids:
            self.user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
        elif self.user_data.get('commcare_location_ids'):
            self.user_data.pop('commcare_location_ids')

        if self.assigned_location_ids and fall_back_to_next:
            new_primary_location_id = self.assigned_location_ids[0]
            self.set_location(SQLLocation.objects.get(location_id=new_primary_location_id))
        else:
            self.user_data.pop('commcare_location_id', None)
            self.user_data.pop('commtrack-supply-point', None)
            self.user_data.pop('commcare_primary_case_sharing_id', None)
            self.location_id = None
            self.clear_location_delegates()
            self.update_fixture_status(UserFixtureType.LOCATION)
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

            if self.assigned_location_ids:
                self.user_data['commcare_location_ids'] = user_location_data(self.assigned_location_ids)
            else:
                self.user_data.pop('commcare_location_ids')
            self.save()

    def _remove_location_from_user(self, location_id):
        from corehq.apps.fixtures.models import UserFixtureType
        try:
            self.assigned_location_ids.remove(location_id)
            self.update_fixture_status(UserFixtureType.LOCATION)
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
        if location_ids:
            self.user_data.update({
                'commcare_location_ids': user_location_data(location_ids)
            })
        else:
            self.user_data.pop('commcare_location_ids', None)

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

    def add_location_delegate(self, location):
        """
        Add a single location to the delgate case access.

        This will dynamically create a supply point if the supply point isn't found.
        """
        # todo: the dynamic supply point creation is bad and should be removed.
        sp = SupplyInterface(self.domain).get_or_create_by_location(location)

        if not location.location_type_object.administrative:
            from corehq.apps.commtrack.util import submit_mapping_case_block
            submit_mapping_case_block(self, self.supply_point_index_mapping(sp))

    def submit_location_block(self, caseblock, source):
        from corehq.apps.hqcase.utils import submit_case_blocks

        submit_case_blocks(
            ElementTree.tostring(
                caseblock.as_xml()
            ).decode('utf-8'),
            self.domain,
            device_id=__name__ + ".CommCareUser." + source,
        )

    def remove_location_delegate(self, location):
        """
        Remove a single location from the case delagate access.
        """

        sp = SupplyInterface(self.domain).get_by_location(location)

        mapping = self.get_location_map_case()

        if not location.location_type_object.administrative:
            if mapping and location.location_id in [loc.location_id for loc in self.locations]:
                caseblock = CaseBlock(
                    create=False,
                    case_id=mapping._id,
                    index=self.supply_point_index_mapping(sp, True)
                )

                self.submit_location_block(caseblock, "remove_location_delegate")

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
            if not location.location_type_object.administrative:
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
            return CaseAccessors(self.domain).get_case(location_map_case_id(self))
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
        return CaseAccessors(self.domain).get_case_by_domain_hq_user_id(self._id, USERCASE_TYPE)

    @quickcache(['self._id'], lambda _: settings.UNIT_TESTING)
    def get_usercase_id(self):
        case = self.get_usercase()
        return case.case_id if case else None

    def update_device_id_last_used(self, device_id, when=None, commcare_version=None, device_app_meta=None):
        """
        Sets the last_used date for the device to be the current time
        Does NOT save the user object.

        :returns: True if user was updated and needs to be saved
        """
        when = when or datetime.utcnow()

        device = self.get_device(device_id)
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
                return True
        else:
            device = DeviceIdLastUsed(device_id=device_id, last_used=when)
            device.update_meta(commcare_version, device_app_meta)
            self.devices.append(device)
            self.last_device = device
            return True
        return False

    def get_last_used_device(self):
        if not self.devices:
            return None

        return max(self.devices, key=lambda dev: dev.last_used)

    def get_device(self, device_id):
        for device in self.devices:
            if device.device_id == device_id:
                return device


def update_fixture_status_for_users(user_ids, fixture_type):
    from corehq.apps.fixtures.models import UserFixtureStatus
    from dimagi.utils.chunked import chunked

    now = datetime.utcnow()
    for ids in chunked(user_ids, 50):
        (UserFixtureStatus.objects
         .filter(user_id__in=ids,
                 fixture_type=fixture_type)
         .update(last_modified=now))
    for user_id in user_ids:
        get_fixture_statuses.clear(user_id)


@quickcache(['user_id'], skip_arg=lambda user_id: settings.UNIT_TESTING)
def get_fixture_statuses(user_id):
    from corehq.apps.fixtures.models import UserFixtureType, UserFixtureStatus
    last_modifieds = {choice[0]: UserFixtureStatus.DEFAULT_LAST_MODIFIED
                      for choice in UserFixtureType.CHOICES}
    for fixture_status in UserFixtureStatus.objects.filter(user_id=user_id):
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

    def to_ota_restore_user(self, domain):
        return OTARestoreWebUser(
            domain,
            self,
        )

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
    def get_users_by_permission(cls, domain, permission):
        user_ids = cls.ids_by_domain(domain)
        for user_doc in iter_docs(cls.get_db(), user_ids):
            web_user = cls.wrap(user_doc)
            if web_user.has_permission(domain, permission):
                yield web_user

    @classmethod
    def get_dimagi_emails_by_domain(cls, domain):
        user_ids = cls.ids_by_domain(domain)
        for user_doc in iter_docs(cls.get_db(), user_ids):
            if user_doc['email'].endswith('@dimagi.com'):
                yield user_doc['email']

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

    def unset_location(self, domain, fall_back_to_next=False):
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

    def reset_locations(self, domain, location_ids):
        """
        reset locations to given list of location_ids. Before calling this, primary location
            should be explicitly set/unset via set_location/unset_location
        """
        membership = self.get_domain_membership(domain)
        membership.assigned_location_ids = location_ids
        if not membership.location_id and location_ids:
            membership.location_id = location_ids[0]
        self.get_sql_locations.reset_cache(self)
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


#
# Django  models go here
#
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
                                    email_from=settings.DEFAULT_FROM_EMAIL)

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
                                    email_from=settings.DEFAULT_FROM_EMAIL)


class SQLInvitation(SyncSQLToCouchMixin, models.Model):
    id = models.IntegerField(db_index=True, null=True)
    uuid = models.UUIDField(primary_key=True, db_index=True, default=uuid4)
    email = models.CharField(max_length=255, db_index=True)
    invited_by = models.CharField(max_length=126)           # couch id of a WebUser
    invited_on = models.DateTimeField()
    is_accepted = models.BooleanField(default=False)
    domain = models.CharField(max_length=255)
    role = models.CharField(max_length=100, null=True)
    program = models.CharField(max_length=126, null=True)   # couch id of a Program
    supply_point = models.CharField(max_length=126, null=True)  # couch id of a Location
    couch_id = models.CharField(max_length=126, null=True, db_index=True)

    class Meta:
        db_table = "users_invitation"

    @classmethod
    def _migration_get_fields(cls):
        return [
            "email",
            "invited_by",
            "invited_on",
            "is_accepted",
            "domain",
            "role",
            "program",
            "supply_point",
        ]

    @classmethod
    def _migration_get_couch_model_class(cls):
        return Invitation

    @classmethod
    def by_domain(cls, domain):
        return SQLInvitation.objects.filter(domain=domain, is_accepted=False)

    @classmethod
    def by_email(cls, email):
        return SQLInvitation.objects.filter(email=email, is_accepted=False)

    @property
    def is_expired(self):
        return self.invited_on.date() + relativedelta(months=1) < datetime.utcnow().date()

    def send_activation_email(self, remaining_days=30):
        inviter = CouchUser.get_by_user_id(self.invited_by)
        url = absolute_reverse("domain_accept_invitation", args=[self.domain, self.uuid])
        params = {
            "domain": self.domain,
            "url": url,
            'days': remaining_days,
            "inviter": inviter.formatted_name,
            'url_prefix': get_static_url_prefix(),
        }

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
                                    email_from=settings.DEFAULT_FROM_EMAIL)


class Invitation(SyncCouchToSQLMixin, QuickCachedDocumentMixin, Document):
    email = StringProperty()
    invited_by = StringProperty()
    invited_on = DateTimeProperty()
    is_accepted = BooleanProperty(default=False)
    domain = StringProperty()
    role = StringProperty()
    program = None
    supply_point = None

    @classmethod
    def _migration_get_fields(cls):
        return [
            "email",
            "invited_by",
            "invited_on",
            "is_accepted",
            "domain",
            "role",
            "program",
            "supply_point",
        ]

    @classmethod
    def _migration_get_sql_model_class(cls):
        return SQLInvitation


class DomainRemovalRecord(DeleteRecord):
    user_id = StringProperty()
    domain_membership = SchemaProperty(DomainMembership)

    def undo(self):
        user = WebUser.get_by_user_id(self.user_id)
        user.add_domain_membership(**self.domain_membership._doc)
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


class AnonymousCouchUser(object):

    username = "public_user"
    doc_type = "CommCareUser"
    _id = 'anonymous_couch_user'

    @property
    def get_id(self):
        return self._id

    @property
    def is_active(self):
        return True

    def is_domain_admin(self):
        return False

    def is_member_of(self, domain):
        return True

    def has_permission(self, domain, perm=None, data=None):
        return False

    def can_view_report(self, domain, report):
        return False

    def can_view_some_reports(self, domain):
        return False

    @property
    def analytics_enabled(self):
        return False

    def can_edit_data(self):
        return False

    def can_edit_apps(self):
        return False

    def is_eula_signed(self, version=None):
        return True

    def is_commcare_user(self):
        return True

    def is_web_user(self):
        return False

    def can_access_any_exports(self, domain):
        return False

    def can_edit_commcare_users(self):
        return False

    def can_view_commcare_users(self):
        return False

    def can_edit_groups(self):
        return False

    def can_view_groups(self):
        return False

    def can_edit_users_in_groups(self):
        return False

    def can_edit_locations(self):
        return False

    def can_view_locations(self):
        return False

    def can_edit_users_in_locations(self):
        return False

    def can_edit_web_users(self):
        return False

    def can_view_web_uers(self):
        return False

    def can_view_roles(self):
        return False


class UserReportingMetadataStaging(models.Model):
    domain = models.TextField()
    user_id = models.TextField()
    app_id = models.TextField(null=True)  # not all form submissions include an app_id
    modified_on = models.DateTimeField(auto_now=True)
    created_on = models.DateTimeField(auto_now=True)

    # should build_id actually be nullable?
    build_id = models.TextField(null=True)

    # The following properties are null if a user has not submitted a form since their last sync
    xform_version = models.IntegerField(null=True)
    form_meta = JSONField(null=True)  # This could be filtered to only the parts we need
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
        app_version, num_unsent_forms, num_quarantined_forms, commcare_version, build_profile_id):
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
        }
        with connection.cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {cls._meta.db_table} AS staging (
                    domain, user_id, app_id, modified_on, created_on,
                    build_id,
                    sync_date, device_id,
                    app_version, num_unsent_forms, num_quarantined_forms,
                    commcare_version, build_profile_id, last_heartbeat
                ) VALUES (
                    %(domain)s, %(user_id)s, %(app_id)s, CLOCK_TIMESTAMP(), CLOCK_TIMESTAMP(),
                    %(build_id)s,
                    %(sync_date)s, %(device_id)s,
                    %(app_version)s, %(num_unsent_forms)s, %(num_quarantined_forms)s,
                    %(commcare_version)s, %(build_profile_id)s, CLOCK_TIMESTAMP()
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
                    last_heartbeat = CLOCK_TIMESTAMP()
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
                save_user=False
            )
        if save:
            user.save(fire_signals=False)

    class Meta(object):
        unique_together = ('domain', 'user_id', 'app_id')
