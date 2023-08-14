import logging
import string
import random
from collections import defaultdict, namedtuple
from datetime import datetime

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


DomainInfo = namedtuple('DomainInfo', [
    'validators', 'can_assign_locations', 'location_cache',
    'roles_by_name', 'profiles_by_name', 'profile_name_by_id', 'group_memoizer'
])


def create_or_update_web_user_invite(email, domain, role_qualified_id, upload_user, location_id,
                                     user_change_logger=None, send_email=True):
    invite, invite_created = Invitation.objects.update_or_create(
        email=email,
        domain=domain,
        is_accepted=False,
        defaults={
            'invited_by': upload_user.user_id,
            'invited_on': datetime.utcnow(),
            'supply_point': location_id,
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


def get_domain_info(
    domain,
    upload_domain,
    user_specs,
    domain_info_by_domain,
    upload_user=None,
    group_memoizer=None,
    is_web_upload=False
):
    from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
    from corehq.apps.users.views.utils import get_editable_role_choices

    domain_info = domain_info_by_domain.get(domain)
    if domain_info:
        return domain_info
    if domain == upload_domain:
        domain_group_memoizer = group_memoizer or GroupMemoizer(domain)
    else:
        domain_group_memoizer = GroupMemoizer(domain)
    domain_group_memoizer.load_all()
    can_assign_locations = domain_has_privilege(domain, privileges.LOCATIONS)
    location_cache = None
    if can_assign_locations:
        location_cache = SiteCodeToLocationCache(domain)

    domain_obj = Domain.get_by_name(domain)
    if domain_obj is None:
        raise UserUploadError(_("Domain cannot be set to '{domain}'".format(domain=domain)))

    allowed_group_names = [group.name for group in domain_group_memoizer.groups]
    profiles_by_name = {}
    profile_name_by_id = {}
    domain_user_specs = [spec for spec in user_specs if spec.get('domain', upload_domain) == domain]
    if is_web_upload:
        roles_by_name = {role[1]: role[0] for role in get_editable_role_choices(domain, upload_user,
                                                                                allow_admin_role=True)}
        validators = get_user_import_validators(
            domain_obj,
            domain_user_specs,
            True,
            allowed_roles=list(roles_by_name),
            upload_domain=upload_domain,
        )
    else:
        roles_by_name = {role.name: role.get_qualified_id() for role in UserRole.objects.get_by_domain(domain)}
        definition = CustomDataFieldsDefinition.get(domain, UserFieldsView.field_type)
        if definition:
            profiles = definition.get_profiles()
            profiles_by_name = {
                profile.name: profile
                for profile in profiles
            }
            profile_name_by_id = {
                profile.pk: profile.name
                for profile in profiles
            }
        validators = get_user_import_validators(
            domain_obj,
            domain_user_specs,
            False,
            allowed_group_names,
            list(roles_by_name),
            list(profiles_by_name),
            upload_domain
        )

    domain_info = DomainInfo(
        validators,
        can_assign_locations,
        location_cache,
        roles_by_name,
        profiles_by_name,
        profile_name_by_id,
        domain_group_memoizer
    )
    domain_info_by_domain[domain] = domain_info
    return domain_info


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
    # HELPME
    #
    # This method has been flagged for refactoring due to its complexity and
    # frequency of touches in changesets
    #
    # If you are writing code that touches this method, your changeset
    # should leave the method better than you found it.
    #
    # Please remove this flag when this method no longer triggers an 'E' or 'F'
    # classification from the radon code static analysis

    from corehq.apps.user_importer.helpers import CommCareUserImporter, WebUserImporter

    domain_info_by_domain = {}

    ret = {"errors": [], "rows": []}
    current = 0
    update_deactivate_after_date = EnterpriseMobileWorkerSettings.is_domain_using_custom_deactivation(
        upload_domain
    )

    for row in user_specs:
        if update_progress:
            update_progress(current)
            current += 1

        username = row.get('username')
        domain = row.get('domain') or upload_domain
        try:
            username = generate_mobile_username(str(username), domain, False) if username else None
        except ValidationError:
            status_row = {
                'username': username,
                'row': row,
                'flag': _("Username must not contain blank spaces or special characters."),
            }
            ret["rows"].append(status_row)
            continue
        status_row = {
            'username': username,
            'row': row,
        }

        # Set a dummy password to pass the validation, similar to GUI user creation
        send_account_confirmation_sms = spec_value_to_boolean_or_none(row, 'send_confirmation_sms')
        if send_account_confirmation_sms and not row.get('password'):
            string_set = string.ascii_uppercase + string.digits + string.ascii_lowercase
            password = ''.join(random.choices(string_set, k=10))
            row['password'] = password

        if row.get('password'):
            row['password'] = str(row.get('password'))
        try:
            domain_info = get_domain_info(domain, upload_domain, user_specs, domain_info_by_domain,
                                          group_memoizer=group_memoizer)
            for validator in domain_info.validators:
                validator(row)
        except UserUploadError as e:
            status_row['flag'] = str(e)
            ret['rows'].append(status_row)
            continue

        data = row.get('data', {})
        email = row.get('email')
        group_names = list(map(str, row.get('group') or []))
        language = row.get('language')
        name = row.get('name')
        password = row.get('password')
        uncategorized_data = row.get('uncategorized_data', {})
        user_id = row.get('user_id')
        location_codes = row.get('location_code', []) if 'location_code' in row else None
        location_codes = format_location_codes(location_codes)
        role = row.get('role', None)
        profile = row.get('user_profile', None)
        web_user_username = row.get('web_user')
        phone_numbers = row.get('phone-number', []) if 'phone-number' in row else None

        deactivate_after = row.get('deactivate_after', None) if update_deactivate_after_date else None
        if isinstance(deactivate_after, datetime):
            deactivate_after = deactivate_after.strftime("%m-%Y")
            row['deactivate_after'] = deactivate_after

        try:
            password = str(password) if password else None
            is_active = spec_value_to_boolean_or_none(row, 'is_active')
            is_account_confirmed = spec_value_to_boolean_or_none(row, 'is_account_confirmed')
            send_account_confirmation_email = spec_value_to_boolean_or_none(row, 'send_confirmation_email')

            remove_web_user = spec_value_to_boolean_or_none(row, 'remove_web_user')

            if send_account_confirmation_sms:
                is_active = False
                if not user_id:
                    is_account_confirmed = False

            user = _get_or_create_commcare_user(domain, user_id, username, is_account_confirmed,
                                                web_user_username, password, upload_user)
            commcare_user_importer = CommCareUserImporter(upload_domain, domain, user, upload_user,
                                                        is_new_user=not bool(user_id),
                                                        via=USER_CHANGE_VIA_BULK_IMPORTER,
                                                        upload_record_id=upload_record_id)
            if user_id:
                if is_password(password):
                    commcare_user_importer.update_password(password)
                    # overwrite password in results so we do not save it to the db
                    status_row['row']['password'] = 'REDACTED'
                status_row['flag'] = 'updated'
            else:
                status_row['flag'] = 'created'

            if phone_numbers is not None:
                phone_numbers = clean_phone_numbers(phone_numbers)
                commcare_user_importer.update_phone_numbers(phone_numbers)

            if name:
                commcare_user_importer.update_name(name)

            commcare_user_importer.update_user_data(data, uncategorized_data, profile, domain_info)

            if update_deactivate_after_date:
                commcare_user_importer.update_deactivate_after(deactivate_after)

            if language:
                commcare_user_importer.update_language(language)
            if email:
                commcare_user_importer.update_email(email)
            if is_active is not None:
                commcare_user_importer.update_status(is_active)

            # Do this here so that we validate the location code before we
            # save any other information to the user, this way either all of
            # the user's information is updated, or none of it
            # Do not update location info if the column is not included at all
            if domain_info.can_assign_locations and location_codes is not None:
                commcare_user_importer.update_locations(location_codes, domain_info)

            if role:
                role_qualified_id = domain_info.roles_by_name[role]
                commcare_user_importer.update_role(role_qualified_id)
            elif not commcare_user_importer.logger.is_new_user and 'role' in row:
                commcare_user_importer.update_role('none')

            if web_user_username:
                user.update_metadata({'login_as_user': web_user_username})

            user.save()
            log = commcare_user_importer.save_log()

            if web_user_username:
                check_can_upload_web_users(domain, upload_user)
                web_user = CouchUser.get_by_username(web_user_username)
                if web_user:
                    web_user_importer = WebUserImporter(upload_domain, domain, web_user, upload_user,
                                                        is_new_user=False,
                                                        via=USER_CHANGE_VIA_BULK_IMPORTER,
                                                        upload_record_id=upload_record_id)
                    user_change_logger = web_user_importer.logger
                else:
                    web_user_importer = None
                    user_change_logger = None
                if remove_web_user:
                    remove_web_user_from_domain(domain, web_user, username, upload_user,
                                                user_change_logger)
                else:
                    check_user_role(username, role)
                    if not web_user and is_account_confirmed:
                        raise UserUploadError(_(
                            "You can only set 'Is Account Confirmed' to 'True' on an existing Web User. "
                            f"{web_user_username} is a new username."
                        ).format(web_user_username=web_user_username))
                    if web_user and not web_user.is_member_of(domain) and is_account_confirmed:
                        # add confirmed account to domain
                        # role_qualified_id would be present here as confirmed in check_user_role
                        web_user_importer.add_to_domain(role_qualified_id, user.location_id)
                    elif not web_user or not web_user.is_member_of(domain):
                        create_or_update_web_user_invite(web_user_username, domain, role_qualified_id,
                                                        upload_user, user.location_id, user_change_logger,
                                                        send_email=send_account_confirmation_email)
                    elif web_user.is_member_of(domain):
                        # edit existing user in the domain
                        web_user_importer.update_role(role_qualified_id)
                        if location_codes is not None:
                            web_user_importer.update_primary_location(user.location_id)
                        web_user.save()
                if web_user_importer:
                    web_user_importer.save_log()
            if not web_user_username:
                if send_account_confirmation_email:
                    send_account_confirmation_if_necessary(user)
                if send_account_confirmation_sms:
                    send_account_confirmation_sms_if_necessary(user)

            if is_password(password):
                # Without this line, digest auth doesn't work.
                # With this line, digest auth works.
                # Other than that, I'm not sure what's going on
                # Passing use_primary_db=True because of https://dimagi-dev.atlassian.net/browse/ICDS-465
                user.get_django_user(use_primary_db=True).check_password(password)

            group_change_message = commcare_user_importer.update_user_groups(domain_info, group_names)

            try:
                domain_info.group_memoizer.save_updated()
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
                ret['errors'].append(_error_message)

            if log and group_change_message:
                log.change_messages.update(group_change_message)
                log.save()
            elif group_change_message:
                log = commcare_user_importer.logger.save_only_group_changes(group_change_message)

        except ValidationError as e:
            status_row['flag'] = e.message
        except (UserUploadError, CouchUser.Inconsistent) as e:
            status_row['flag'] = str(e)

        ret["rows"].append(status_row)

    return ret


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
    from corehq.apps.user_importer.helpers import WebUserImporter

    domain_info_by_domain = {}

    ret = {"errors": [], "rows": []}
    current = 0

    for row in user_specs:
        if update_progress:
            update_progress(current)
            current += 1

        username = row.get('username')
        domain = row.get('domain') or upload_domain
        status_row = {
            'username': username,
            'row': row,
        }
        try:
            domain_info = get_domain_info(domain, upload_domain, user_specs, domain_info_by_domain,
                                          upload_user=upload_user, is_web_upload=True)
            for validator in domain_info.validators:
                validator(row)
        except UserUploadError as e:
            status_row['flag'] = str(e)
            ret['rows'].append(status_row)
            continue

        role = row.get('role', None)
        status = row.get('status')

        location_codes = row.get('location_code', []) if 'location_code' in row else None
        location_codes = format_location_codes(location_codes)

        try:
            remove = spec_value_to_boolean_or_none(row, 'remove')
            check_user_role(username, role)
            role_qualified_id = domain_info.roles_by_name[role]
            check_can_upload_web_users(domain, upload_user)

            user = CouchUser.get_by_username(username, strict=True)
            if user:
                check_changing_username(user, username)
                web_user_importer = WebUserImporter(upload_domain, domain, user, upload_user,
                                                    is_new_user=False,
                                                    via=USER_CHANGE_VIA_BULK_IMPORTER,
                                                    upload_record_id=upload_record_id)
                user_change_logger = web_user_importer.logger
                if remove:
                    remove_web_user_from_domain(domain, user, username, upload_user, user_change_logger,
                                                is_web_upload=True)
                else:
                    membership = user.get_domain_membership(domain)
                    if membership:
                        modify_existing_user_in_domain(upload_domain, domain, domain_info, location_codes,
                                                       membership, role_qualified_id, upload_user, user,
                                                       web_user_importer)
                    else:
                        create_or_update_web_user_invite(username, domain, role_qualified_id, upload_user,
                                                         user.location_id, user_change_logger)
                web_user_importer.save_log()
                status_row['flag'] = 'updated'

            else:
                if remove:
                    remove_invited_web_user(domain, username)
                    status_row['flag'] = 'updated'
                else:
                    if status == "Invited":
                        try:
                            invitation = Invitation.objects.get(domain=domain, email=username, is_accepted=False)
                        except Invitation.DoesNotExist:
                            raise UserUploadError(_("You can only set 'Status' to 'Invited' on a pending Web "
                                                    "User. {web_user} has no invitations for this project "
                                                    "space.").format(web_user=username))
                        if invitation.email_status == InvitationStatus.BOUNCED and invitation.email == username:
                            raise UserUploadError(_("The email has bounced for this user's invite. Please try "
                                                    "again with a different username").format(web_user=username))
                    user_invite_loc_id = None
                    if domain_info.can_assign_locations and location_codes is not None:
                        # set invite location to first item in location_codes
                        if len(location_codes) > 0:
                            user_invite_loc = get_location_from_site_code(
                                location_codes[0], domain_info.location_cache
                            )
                            user_invite_loc_id = user_invite_loc.location_id
                    create_or_update_web_user_invite(username, domain, role_qualified_id, upload_user,
                                                     user_invite_loc_id)
                    status_row['flag'] = 'invited'

        except (UserUploadError, CouchUser.Inconsistent) as e:
            status_row['flag'] = str(e)

        ret["rows"].append(status_row)

    return ret


def modify_existing_user_in_domain(upload_domain, domain, domain_info, location_codes, membership,
                                   role_qualified_id, upload_user, current_user, web_user_importer,
                                   max_tries=3):
    if domain_info.can_assign_locations and location_codes is not None:
        web_user_importer.update_locations(location_codes, membership, domain_info)
    web_user_importer.update_role(role_qualified_id)
    try:
        current_user.save()
    except ResourceConflict:
        notify_exception(None, message="ResouceConflict during web user import",
                         details={'domain': domain, 'username': current_user.username})
        if max_tries > 0:
            current_user.clear_quickcache_for_user()
            updated_user = CouchUser.get_by_username(current_user.username, strict=True)
            modify_existing_user_in_domain(domain, domain_info, location_codes, membership, role_qualified_id,
                                           upload_user, updated_user, web_user_importer, max_tries=max_tries - 1)
        else:
            raise


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
