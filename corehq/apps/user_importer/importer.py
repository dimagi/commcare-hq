import copy
import logging
import string
import random
from collections import defaultdict, namedtuple
from datetime import datetime
from corehq.util.soft_assert.api import soft_assert

from memoized import memoized
from django.db import DEFAULT_DB_ALIAS

from corehq.apps.enterprise.models import EnterpriseMobileWorkerSettings
from corehq.apps.users.util import generate_mobile_username
from dimagi.utils.logging import notify_exception
from django.utils.translation import gettext as _

from couchdbkit.exceptions import (
    BulkSaveError,
    MultipleResultsFound,
    ResourceNotFound,
    ResourceConflict
)

from django.core.exceptions import ValidationError
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.commtrack.util import get_supply_point_and_location
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
)
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.helpers import (
    spec_value_to_boolean_or_none,
)
from corehq.apps.user_importer.validation import (
    get_user_import_validators,
    is_password,
)
from corehq.apps.users.audit.change_messages import UserChangeMessage
from corehq.apps.users.account_confirmation import (
    send_account_confirmation_if_necessary,
    send_account_confirmation_sms_if_necessary,
)
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Invitation,
    UserRole,
    InvitationStatus
)
from corehq.const import USER_CHANGE_VIA_BULK_IMPORTER
from corehq.toggles import DOMAIN_PERMISSIONS_MIRROR, TABLEAU_USER_SYNCING
from corehq.apps.sms.util import validate_phone_number

from dimagi.utils.logging import notify_error

required_headers = set(['username'])
web_required_headers = set(['username', 'role'])
allowed_headers = set([
    'data', 'email', 'group', 'language', 'name', 'password', 'phone-number',
    'uncategorized_data', 'user_id', 'is_active', 'is_account_confirmed', 'send_confirmation_email',
    'location_code', 'role', 'user_profile',
    'User IMEIs (read only)', 'registered_on (read only)', 'last_submission (read only)',
    'last_sync (read only)', 'web_user', 'remove_web_user', 'remove', 'last_access_date (read only)',
    'last_login (read only)', 'last_name', 'status', 'first_name',
    'send_confirmation_sms',
]) | required_headers
old_headers = {
    # 'old_header_name': 'new_header_name'
    'location-sms-code': 'location_code'
}


def check_headers(user_specs, domain, is_web_upload=False):
    messages = []
    headers = set(user_specs.fieldnames)

    # Backwards warnings
    for (old_name, new_name) in old_headers.items():
        if old_name in headers:
            messages.append(
                _("'The column header '{old_name}' is deprecated, please use '{new_name}' instead.").format(
                    old_name=old_name, new_name=new_name
                ))
            headers.discard(old_name)

    if DOMAIN_PERMISSIONS_MIRROR.enabled(domain):
        allowed_headers.add('domain')

    if not is_web_upload and EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(domain):
        allowed_headers.add('deactivate_after')

    if TABLEAU_USER_SYNCING.enabled(domain):
        allowed_headers.update({'tableau_role', 'tableau_groups'})

    illegal_headers = headers - allowed_headers

    if is_web_upload:
        missing_headers = web_required_headers - headers
    else:
        missing_headers = required_headers - headers

    for header_set, label in (missing_headers, 'required'), (illegal_headers, 'illegal'):
        if header_set:
            messages.append(_('The following are {label} column headers: {headers}.').format(
                label=label, headers=', '.join(header_set)))
    if messages:
        raise UserUploadError('\n'.join(messages))


class GroupMemoizer(object):
    """

    If you use this to get a group, do not set group.name directly;
    use group_memoizer.rename_group(group, name) instead.
    """

    def __init__(self, domain):
        self.groups_by_name = {}
        self.groups_by_id = {}
        self.groups = set()
        self.updated_groups = set()
        self.domain = domain
        self.groups_by_user_id = defaultdict(set)
        self.loaded = False

    def load_all(self):
        if not self.loaded:
            for group in Group.by_domain(self.domain):
                self.add_group(group)
            self.loaded = True

    def add_group(self, new_group):
        # todo
        # this has the possibility of missing two rows one with id one with name
        # that actually refer to the same group
        # and overwriting one with the other
        assert new_group.name
        if new_group.get_id:
            self.groups_by_id[new_group.get_id] = new_group
            for user_id in new_group.users:
                self.groups_by_user_id[user_id].add(new_group.get_id)
        self.groups_by_name[new_group.name] = new_group
        self.groups.add(new_group)

    def by_name(self, group_name):
        if group_name not in self.groups_by_name:
            group = Group.by_name(self.domain, group_name)
            if not group:
                self.groups_by_name[group_name] = None
                return None
            self.add_group(group)
        return self.groups_by_name[group_name]

    def by_user_id(self, user_id):
        group_ids = self.groups_by_user_id.get(user_id)
        if not group_ids:
            return []
        return [
            self.get(group_id) for group_id in group_ids
        ]

    def get(self, group_id):
        if group_id not in self.groups_by_id:
            group = Group.get(group_id)
            if group.domain != self.domain:
                raise ResourceNotFound()
            self.add_group(group)
        return self.groups_by_id[group_id]

    def create(self, domain, name):
        group = Group(domain=domain, name=name)
        self.add_group(group)
        return group

    def rename_group(self, group, name):
        # This isn't always true, you can rename A => B and then B => C,
        # and what was A will now be called B when you try to change
        # what was B to be called C. That's fine, but you don't want to
        # delete someone else's entry
        if self.groups_by_name.get(group.name) is group:
            del self.groups_by_name[group.name]
        group.name = name
        self.add_group(group)

    def group_updated(self, group_id):
        self.updated_groups.add(group_id)

    def save_updated(self):
        updated = [self.groups_by_id[_id] for _id in self.updated_groups]
        Group.bulk_save(updated)
        self.updated_groups.clear()

    def save_all(self):
        Group.bulk_save(self.groups)


class BulkCacheBase(object):

    def __init__(self, domain):
        self.domain = domain
        self.cache = {}

    def get(self, key):
        if not key:
            return None
        if key not in self.cache:
            self.cache[key] = self.lookup(key)
        return self.cache[key]

    def lookup(self, key):
        # base classes must implement this themselves
        raise NotImplementedError


class SiteCodeToSupplyPointCache(BulkCacheBase):
    """
    Cache the lookup of a supply point object from
    the site code used in upload.
    """

    def lookup(self, site_code):
        case_location = get_supply_point_and_location(
            self.domain,
            site_code
        )
        return case_location.case


class SiteCodeToLocationCache(BulkCacheBase):

    def __init__(self, domain):
        self.non_admin_types = [
            loc_type.name for loc_type in Domain.get_by_name(domain).location_types
            if not loc_type.administrative
        ]
        super(SiteCodeToLocationCache, self).__init__(domain)

    def lookup(self, site_code):
        """
        Note that this can raise SQLLocation.DoesNotExist if the location with the
        given site code is not found.
        """
        return SQLLocation.objects.using(DEFAULT_DB_ALIAS).get(
            domain=self.domain,
            site_code__iexact=site_code
        )


def create_or_update_groups(domain, group_specs):
    log = {"errors": []}
    group_memoizer = GroupMemoizer(domain)
    group_memoizer.load_all()
    group_names = set()
    for row in group_specs:
        group_id = row.get('id')
        group_name = str(row.get('name') or '')
        case_sharing = row.get('case-sharing')
        reporting = row.get('reporting')
        data = row.get('data')

        # check that group_names are unique
        if group_name in group_names:
            log['errors'].append(
                'Your spreadsheet has multiple groups called "%s" and only the first was processed' % group_name
            )
            continue
        else:
            group_names.add(group_name)

        # check that there's a group_id or a group_name
        if not group_id and not group_name:
            log['errors'].append('Your spreadsheet has a group with no name or id and it has been ignored')
            continue

        try:
            if group_id:
                group = group_memoizer.get(group_id)
            else:
                group = group_memoizer.by_name(group_name)
                if not group:
                    group = group_memoizer.create(domain=domain, name=group_name)
                    group.save()
        except ResourceNotFound:
            log["errors"].append('There are no groups on CommCare HQ with id "%s"' % group_id)
        except MultipleResultsFound:
            log["errors"].append("There are multiple groups on CommCare HQ named: %s" % group_name)
        else:
            if group_name:
                group_memoizer.rename_group(group, group_name)
            group.case_sharing = case_sharing
            group.reporting = reporting
            group.metadata = data
            group.save()
    return group_memoizer, log


def get_location_from_site_code(site_code, location_cache):
    if isinstance(site_code, str):
        site_code = site_code.lower()
    elif isinstance(site_code, int):
        site_code = str(site_code)
    else:
        raise UserUploadError(
            _("Unexpected format received for site code '%(site_code)s'") %
            {'site_code': site_code}
        )

    try:
        return location_cache.get(site_code)
    except SQLLocation.DoesNotExist:
        raise UserUploadError(
            _("Could not find organization with site code '%(site_code)s'") %
            {'site_code': site_code}
        )


def create_or_update_web_user_invite(email, domain, role_qualified_id, upload_user, location_id,
                                     user_change_logger=None, send_email=True):
    # Preparation for location to replace supply_point
    invite, invite_created = Invitation.objects.update_or_create(
        email=email,
        domain=domain,
        is_accepted=False,
        defaults={
            'invited_by': upload_user.user_id,
            'invited_on': datetime.utcnow(),
            'supply_point': location_id,
            'location': SQLLocation.by_location_id(location_id),
            'role': role_qualified_id
        },
    )
    if invite_created and send_email:
        invite.send_activation_email()
    if invite_created and user_change_logger:
        user_change_logger.add_info(UserChangeMessage.invited_to_domain(domain))


def find_location_id(location_codes, location_cache):
    location_ids = []
    for code in location_codes:
        loc = get_location_from_site_code(code, location_cache)
        location_ids.append(loc.location_id)
    return location_ids


def check_modified_user_loc(location_ids, loc_id, assigned_loc_ids):
    locations_updated = set(assigned_loc_ids) != set(location_ids)
    primary_location_removed = bool(loc_id and (not location_ids or loc_id not in location_ids))
    return locations_updated, primary_location_removed


def format_location_codes(location_codes):
    if location_codes and not isinstance(location_codes, list):
        location_codes = [location_codes]
    if location_codes is not None:
        # ignore empty
        location_codes = [code for code in location_codes if code]
    return location_codes


def clean_phone_numbers(phone_numbers):
    cleaned_numbers = []
    for number in phone_numbers:
        if number:
            validate_phone_number(number, f'Invalid phone number detected: {number}')
            cleaned_numbers.append(number)
    return cleaned_numbers


def create_or_update_commcare_users_and_groups(upload_domain, user_specs, upload_user, upload_record_id,
                                               group_memoizer=None,
                                               update_progress=None):
    """
    Creates and Updates CommCare Users
    For the associated web user username passed, for each CommCareUser
        if corresponding web user is present
            if web user has confirmed account but not a member of domain
                adds them to the domain with same role and primary location as the CommCareUser
            if already a member of domain
                update their role and primary location to be same as that of the CommCareUser
        else creates or updates user invitation
           sets Invitation with the CommCare user's role and primary location
    All changes to users only, are tracked using UserChangeLogger, as an audit trail.
    """
    return CCImporter(
        upload_domain, user_specs, upload_user, upload_record_id,
        group_memoizer=group_memoizer,
        update_progress=update_progress
    ).run()


class BaseUserRow:
    def __init__(self, importer, row):
        self.importer = importer
        self.row = row
        self.status_row = {
            'username': row.get('username'),
            'row': copy.copy(row)
        }
        self.error = None
        self.domain = self.row.get('domain') or self.importer.upload_domain
        self.domain_info = self.importer.domain_info(self.domain)
        self.column_values = {}

    def validate_row(self):
        for validator in self.domain_info.validators:
            validator(self.row)


class CCUserRow(BaseUserRow):

    def process(self):
        if not self._process_column_values():
            return False

        try:
            self.validate_row()
            self._process_simple_fields()

            try:
                self.user.save(fail_hard=True)
            except Exception as e:
                # HACK: Catching all exception here is temporary. We believe that user critical sections
                # are not behaving properly, and this catch-all is here to identify the problem
                self.status_row['flag'] = str(e)
                notify_error(f'Error while processing bulk import: {str(e)}')
                soft_assert(to='{}@{}'.format('mriley', 'dimagi.com'), send_to_ops=False)(
                    False,
                    'Error while processing bulk import',
                    e
                )
                return False

            log = self.import_helper.save_log()

            self._process_web_user()

            if is_password(self.column_values["password"]):
                # Without this line, digest auth doesn't work.
                # With this line, digest auth works.
                # Other than that, I'm not sure what's going on
                # Passing use_primary_db=True because of https://dimagi-dev.atlassian.net/browse/ICDS-465
                self.user.get_django_user(use_primary_db=True).check_password(self.column_values["password"])

            group_change_message = self.import_helper.update_user_groups(
                self.domain_info, self.column_values["group_names"]
            )

            try:
                self.domain_info.group_memoizer.save_updated()
            except BulkSaveError as e:
                _error_message = (
                    "Oops! We were not able to save some of your group changes. "
                    "Please make sure no one else is editing your groups "
                    "and try again."
                )
                logging.exception((
                    'BulkSaveError saving groups. '
                    'User saw error message "%s". Errors: %s'
                ) % (_error_message, e.errors))
                self.error = _error_message

            if log and group_change_message:
                log.change_messages.update(group_change_message)
                log.save()
            elif group_change_message:
                log = self.import_helper.logger.save_only_group_changes(group_change_message)

        except ValidationError as e:
            self.status_row['flag'] = e.message
        except (UserUploadError, CouchUser.Inconsistent) as e:
            self.status_row['flag'] = str(e)

    def _parse_username(self):
        username = self.row.get('username')
        try:
            self.column_values['username'] = generate_mobile_username(str(username), self.domain, False) if username else None
        except ValidationError as e:
            self.status_row['flag'] = _("Username must not contain blank spaces or special characters.")
            self.column_values['username'] = username
            return False
        return True

    def _parse_password(self):
        if self.row.get('password'):
            password = str(self.row.get('password'))
        elif self.column_values["send_confirmation_sms"]:
            # Set a dummy password to pass the validation, similar to GUI user creation
            string_set = string.ascii_uppercase + string.digits + string.ascii_lowercase
            password = ''.join(random.choices(string_set, k=10))
        else:
            password = None
        self.column_values['password'] = password
        self.status_row['row']['password'] = ''
        if self.column_values['user_id'] and is_password(password):
            self.status_row['row']['password'] = 'REDACTED'

    def _process_column_values(self):
        values = {
            "data": self.row.get('data', {}),
            "email": self.row.get('email'),
            "group_names": list(map(str, self.row.get('group') or [])),
            "language": self.row.get('language'),
            "name": self.row.get('name'),
            "uncategorized_data": self.row.get('uncategorized_data', {}),
            "user_id": self.row.get('user_id'),
            "location_codes": format_location_codes(
                self.row.get('location_code', []) if 'location_code' in self.row else None
            ),
            "role": self.row.get('role', None),
            "profile_name": self.row.get('user_profile', None),
            "web_user_username": self.row.get('web_user'),
            "phone_numbers": self.row.get('phone-number', []) if 'phone-number' in self.row else None,
            "deactivate_after": self.row.get('deactivate_after', None)
        }

        for v in ['is_active', 'is_account_confirmed', 'send_confirmation_email', 'remove_web_user', 'send_confirmation_sms']:
            values[v] = spec_value_to_boolean_or_none(self.row, v)

        if values["send_confirmation_sms"] and not values["user_id"]:
            values["is_account_confirmed"] = False
        else:
            values["is_account_confirmed"] = values["is_account_confirmed"]

        self.column_values.update(values)
        if not self._parse_username():
            return False
        self._parse_password()
        return True

    @property
    @memoized
    def user(self):
        cv = self.column_values
        self.status_row['flag'] = 'updated' if cv['user_id'] else 'created'
        return _get_or_create_commcare_user(
            self.domain, cv["user_id"], cv["username"], cv["is_account_confirmed"],
            cv["web_user_username"], cv["password"], self.importer.upload_user
        )

    @property
    @memoized
    def import_helper(self):
        from corehq.apps.user_importer.helpers import CommCareUserImporter
        return CommCareUserImporter(
            self.importer.upload_domain, self.domain, self.user, self.importer.upload_user,
            is_new_user=not bool(self.column_values["user_id"]),
            via=USER_CHANGE_VIA_BULK_IMPORTER,
            upload_record_id=self.importer.upload_record_id
        )

    def _process_simple_fields(self):
        cv = self.column_values
        # process password
        if cv["user_id"] and is_password(cv["password"]):
            self.user.set_password(cv["password"])
            self.import_helper.logger.add_change_message(UserChangeMessage.password_reset())

        # process phone_numbers
        if cv["phone_numbers"] is not None:
            phone_numbers = clean_phone_numbers(cv["phone_numbers"])
            self.import_helper.update_phone_numbers(phone_numbers)

        # process name
        if cv["name"]:
            self.user.set_full_name(str(cv["name"]))
            self.import_helper.logger.add_changes(
                {'first_name': self.user.first_name, 'last_name': self.user.last_name}
            )

        # process user_data
        self.import_helper.update_user_data(
            cv["data"], cv["uncategorized_data"], cv["profile_name"],
            self.domain_info.profiles_by_name
        )

        if self.importer.update_deactivate_after_date:
            deactivate_after = cv['deactivate_after']
            if isinstance(deactivate_after, datetime):
                deactivate_after = deactivate_after.strftime("%m-%Y")

            self.import_helper.update_deactivate_after(deactivate_after)

        if cv["language"]:
            self.import_helper.update_language(cv["language"])
        if cv["email"]:
            self.import_helper.update_email(cv["email"])
        if cv["is_active"] is not None:
            self.import_helper.update_status(cv["is_active"])

        # Do this here so that we validate the location code before we
        # save any other information to the user, this way either all of
        # the user's information is updated, or none of it
        # Do not update location info if the column is not included at all
        if self.domain_info.can_assign_locations and cv["location_codes"] is not None:
            self.import_helper.update_locations(cv["location_codes"], self.domain_info)

        if cv["role"]:
            role_qualified_id = self.domain_info.roles_by_name[cv["role"]]
            self.import_helper.update_role(role_qualified_id)
        elif not self.import_helper.logger.is_new_user and cv["role"]:
            self.import_helper.update_role('none')

        if cv["web_user_username"]:
            self.user.get_user_data(self.domain)['login_as_user'] = cv["web_user_username"]

    def _process_web_user(self):
        from corehq.apps.user_importer.helpers import WebUserImporter
        cv = self.column_values
        web_user_username = cv["web_user_username"]
        if web_user_username:
            check_can_upload_web_users(self.domain, self.importer.upload_user)
            web_user = CouchUser.get_by_username(web_user_username)
            if web_user:
                web_user_importer = WebUserImporter(self.importer.upload_domain, self.domain, web_user, self.importer.upload_user,
                                                    is_new_user=False,
                                                    via=USER_CHANGE_VIA_BULK_IMPORTER,
                                                    upload_record_id=self.importer.upload_record_id)
                user_change_logger = web_user_importer.logger
            else:
                web_user_importer = None
                user_change_logger = None
            if cv["remove_web_user"]:
                remove_web_user_from_domain(self.domain, web_user, cv["username"], self.importer.upload_user,
                                            user_change_logger)
            else:
                check_user_role(cv["username"], cv["role"])
                if not web_user and cv["is_account_confirmed"]:
                    raise UserUploadError(_(
                        "You can only set 'Is Account Confirmed' to 'True' on an existing Web User. "
                        f"{web_user_username} is a new username."
                    ).format(web_user_username=web_user_username))
                role_qualified_id = self.domain_info.roles_by_name[cv["role"]]
                if web_user and not web_user.is_member_of(self.domain) and cv["is_account_confirmed"]:
                    # add confirmed account to domain
                    # role_qualified_id would be present here as confirmed in check_user_role
                    web_user_importer.add_to_domain(role_qualified_id, self.user.location_id)
                elif not web_user or not web_user.is_member_of(self.domain):
                    create_or_update_web_user_invite(web_user_username, self.domain, role_qualified_id,
                                                    self.importer.upload_user, self.user.location_id, user_change_logger,
                                                    send_email=cv["send_confirmation_email"])
                elif web_user.is_member_of(self.domain):
                    # edit existing user in the domain
                    web_user_importer.update_role(role_qualified_id)
                    if cv["location_codes"] is not None:
                        web_user_importer.update_primary_location(self.user.location_id)
                    web_user.save()
            if web_user_importer:
                web_user_importer.save_log()
        else:
            if cv["send_confirmation_email"]:
                send_account_confirmation_if_necessary(self.user)
            if cv["send_confirmation_sms"]:
                send_account_confirmation_sms_if_necessary(self.user)


class WebUserRow(BaseUserRow):

    def _process_column_values(self):
        self.column_values = {
            'username': self.row.get('username'),
            'role': self.row.get('role'),
            'status': self.row.get('status'),
            'location_codes': format_location_codes(self.row.get('location_code', [])),
            'remove': spec_value_to_boolean_or_none(self.row, 'remove'),
            "data": self.row.get('data', {}),
            "uncategorized_data": self.row.get('uncategorized_data', {}),
            "profile_name": self.row.get('user_profile', None),
        }

    def process(self):
        try:
            self.validate_row()
            self._process_column_values()
            self.process_row()
        except UserUploadError as e:
            self.status_row['flag'] = str(e)

    def process_row(self):
        user = CouchUser.get_by_username(self.column_values['username'], strict=True)
        if user:
            self.process_existing_user(user)
        else:
            self.process_new_user()

    def process_existing_user(self, user):
        from corehq.apps.user_importer.helpers import WebUserImporter
        check_changing_username(user, user.username)
        web_user_importer = WebUserImporter(
            self.importer.upload_domain, self.domain, user, self.importer.upload_user,
            is_new_user=False, via=USER_CHANGE_VIA_BULK_IMPORTER, upload_record_id=self.importer.upload_record_id
        )
        user_change_logger = web_user_importer.logger

        if self.column_values['remove']:
            remove_web_user_from_domain(
                self.domain, user, user.username, self.importer.upload_user, user_change_logger, is_web_upload=True
            )
            self.status_row['flag'] = 'updated'
        else:
            membership = user.get_domain_membership(self.domain)
            role_qualified_id = self.domain_info.roles_by_name[self.column_values['role']]

            if membership:
                self._modify_existing_user_in_domain(
                    membership, role_qualified_id, user, web_user_importer
                )
            else:
                create_or_update_web_user_invite(
                    user.username, self.domain, role_qualified_id, self.importer.upload_user,
                    user.location_id, user_change_logger
                )
        web_user_importer.save_log()
        self.status_row['flag'] = 'updated'

    def _modify_existing_user_in_domain(self, membership, role_qualified_id,
                                       current_user, web_user_importer,
                                       max_tries=3):
        cv = self.column_values
        # set locations
        location_codes = cv['location_codes']
        if self.domain_info.can_assign_locations and location_codes is not None:
            web_user_importer.update_locations(location_codes, membership, self.domain_info)

        # set role
        web_user_importer.update_role(role_qualified_id)

        # set user_data
        web_user_importer.update_user_data(
            cv["data"], cv["uncategorized_data"], cv["profile_name"],
            self.domain_info.profiles_by_name
        )

        # Try saving
        try:
            current_user.save()
        except ResourceConflict:
            notify_exception(None, message="ResouceConflict during web user import",
                             details={'domain': self.domain, 'username': current_user.username})
            if max_tries > 0:
                current_user.clear_quickcache_for_user()
                updated_user = CouchUser.get_by_username(current_user.username, strict=True)
                self._modify_existing_user_in_domain(
                    membership, role_qualified_id,
                    updated_user, web_user_importer, max_tries=max_tries - 1)
            else:
                raise

    def process_new_user(self):
        cv = self.column_values

        if cv['remove']:
            remove_invited_web_user(self.domain, cv['username'])
            self.status_row['flag'] = 'updated'
        else:
            if cv['status'] == "Invited":
                self.check_invitation_status(self.domain, cv['username'])

            user_invite_loc_id = None
            if self.domain_info.can_assign_locations and cv['location_codes']:
                if len(cv['location_codes']) > 0:
                    user_invite_loc = get_location_from_site_code(
                        cv['location_codes'][0], self.domain_info.location_cache
                    )
                    user_invite_loc_id = user_invite_loc.location_id

            create_or_update_web_user_invite(
                cv['username'], self.domain, self.domain_info.roles_by_name[cv['role']], self.importer.upload_user,
                user_invite_loc_id
            )
            self.status_row['flag'] = 'invited'

    def check_invitation_status(self, domain, username):
        try:
            invitation = Invitation.objects.get(domain=domain, email=username, is_accepted=False)
        except Invitation.DoesNotExist:
            raise UserUploadError(
                _("You can only set 'Status' to 'Invited' on a pending Web User. "
                "{web_user} has no invitations for this project space.").format(web_user=username)
            )

        if invitation.email_status == InvitationStatus.BOUNCED and invitation.email == username:
            raise UserUploadError(_("The email has bounced for this user's invite. "
                                "Please try again with a different username").format(web_user=username))


class WebImporter:

    row_cls = WebUserRow

    def __init__(self, upload_domain, user_specs, upload_user, upload_record_id,
                 update_progress=None):
        self.upload_domain = upload_domain
        self.user_specs = user_specs
        self.upload_user = upload_user
        self.upload_record_id = upload_record_id
        self.update_progress = update_progress
        self.is_web_upload = True

    @memoized
    def domain_info(self, domain):
        return DomainInfo(self, domain, is_web_upload=self.is_web_upload)

    def run(self):
        ret = {"errors": [], "rows": []}
        current = 0
        for i, row in enumerate(self.user_specs):
            if self.update_progress:
                self.update_progress(i)
            user_row = self.row_cls(self, row)
            user_row.process()
            ret["rows"].append(user_row.status_row)
            if user_row.error:
                ret["errors"].append(user_row.error)
        return ret


class CCImporter(WebImporter):

    row_cls = CCUserRow

    def __init__(self, *args, group_memoizer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._group_memoizer = group_memoizer
        self.is_web_upload = False

    @property
    @memoized
    def update_deactivate_after_date(self):
        return EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
            self.upload_domain
        )


class DomainInfo:

    def __init__(self, importer, domain, is_web_upload):
        self.importer = importer
        self.domain = domain
        self.is_web_upload = is_web_upload

    @property
    @memoized
    def domain_obj(self):
        domain_obj = Domain.get_by_name(self.domain)
        if domain_obj is None:
            raise UserUploadError(_(f"Domain cannot be set to '{self.domain}'"))
        return domain_obj

    @property
    @memoized
    def group_memoizer(self):
        if self.domain == self.importer.upload_domain:
            memoizer = self.importer._group_memoizer or GroupMemoizer(self.domain)
        else:
            memoizer = GroupMemoizer(self.domain)
        memoizer.load_all()
        return memoizer

    @property
    @memoized
    def roles_by_name(self):
        from corehq.apps.users.views.utils import get_editable_role_choices
        if self.is_web_upload:
            return {role[1]: role[0] for role in get_editable_role_choices(self.domain, self.importer.upload_user,
                                                  allow_admin_role=True)}
        else:
            return {role.name: role.get_qualified_id() for role in UserRole.objects.get_by_domain(self.domain)}

    @property
    @memoized
    def can_assign_locations(self):
        return domain_has_privilege(self.domain, privileges.LOCATIONS)

    @property
    @memoized
    def location_cache(self):
        if self.can_assign_locations:
            return SiteCodeToLocationCache(self.domain)
        else:
            return None

    @property
    @memoized
    def profiles_by_name(self):
        from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
        definition = CustomDataFieldsDefinition.get(self.domain, UserFieldsView.field_type)
        if definition:
            profiles = definition.get_profiles()
            return {
                profile.name: profile
                for profile in profiles
            }
        else:
            return {}

    @property
    @memoized
    def validators(self):
        roles_by_name = list(self.roles_by_name)
        domain_user_specs = [
            spec
            for spec in self.importer.user_specs if spec.get('domain', self.importer.upload_domain) == self.domain
        ]
        if self.is_web_upload:
            allowed_group_names = None
        else:
            allowed_group_names = [group.name for group in self.group_memoizer.groups]
        return get_user_import_validators(
            self.domain_obj,
            domain_user_specs,
            self.is_web_upload,
            allowed_group_names,
            allowed_roles=roles_by_name,
            profiles_by_name=self.profiles_by_name,
            upload_domain=self.importer.upload_domain,
        )


def _get_or_create_commcare_user(domain, user_id, username, is_account_confirmed, web_user_username, password,
                                 upload_user):
    if user_id:
        user = CommCareUser.get_by_user_id(user_id, domain)
        if not user:
            raise UserUploadError(_(
                "User with ID '{user_id}' not found"
            ).format(user_id=user_id, domain=domain))
        check_changing_username(user, username)

        # note: explicitly not including "None" here because that's the default value if not set.
        # False means it was set explicitly to that value
        if is_account_confirmed is False and not web_user_username:
            raise UserUploadError(_(
                "You can only set 'Is Account Confirmed' to 'False' on a new User."
            ))
    else:
        kwargs = {}
        if is_account_confirmed is not None and not web_user_username:
            kwargs['is_account_confirmed'] = is_account_confirmed
        user = CommCareUser.create(domain, username, password, created_by=upload_user,
                                   created_via=USER_CHANGE_VIA_BULK_IMPORTER, commit=False, **kwargs)
    return user


def create_or_update_web_users(upload_domain, user_specs, upload_user, upload_record_id, update_progress=None):
    return WebImporter(
        upload_domain, user_specs, upload_user, upload_record_id,
        update_progress=update_progress
    ).run()


def check_user_role(username, role):
    if not role:
        raise UserUploadError(_(
            "You cannot upload a web user without a role. {username} does not have "
            "a role").format(username=username))


def check_can_upload_web_users(domain, upload_user):
    if not upload_user.can_edit_web_users(domain):
        raise UserUploadError(_(
            "Only users with the edit web users permission can upload web users"
        ))


def check_changing_username(user, username):
    if username and user.username != username:
        raise UserUploadError(_(
            'Changing usernames is not supported: %(username)r to %(new_username)r'
        ) % {'username': user.username, 'new_username': username})


def remove_invited_web_user(domain, username):
    try:
        invitation = Invitation.objects.get(domain=domain, email=username)
    except Invitation.DoesNotExist:
        raise UserUploadError(_("You cannot remove a web user that is not a member or invited to this project. "
                                "{username} is not a member or invited.").format(username=username))
    invitation.delete()


def remove_web_user_from_domain(domain, user, username, upload_user, user_change_logger=None,
                                is_web_upload=False):
    if not user or not user.is_member_of(domain):
        if is_web_upload:
            remove_invited_web_user(domain, username)
            if user_change_logger:
                user_change_logger.add_info(UserChangeMessage.invitation_revoked_for_domain(domain))
        else:
            raise UserUploadError(_("You cannot remove a web user that is not a member of this project."
                                    " {web_user} is not a member.").format(web_user=user))
    elif username == upload_user.username:
        raise UserUploadError(_("You cannot remove yourself from a domain via bulk upload"))
    else:
        user.delete_domain_membership(domain)
        user.save()
        if user_change_logger:
            user_change_logger.add_info(UserChangeMessage.domain_removal(domain))
