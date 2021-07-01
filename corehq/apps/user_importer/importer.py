import logging
from collections import defaultdict, namedtuple
from datetime import datetime

from django.db import DEFAULT_DB_ALIAS
from dimagi.utils.logging import notify_exception
from django.utils.translation import ugettext as _

from couchdbkit.exceptions import (
    BulkSaveError,
    MultipleResultsFound,
    ResourceNotFound,
    ResourceConflict
)

from dimagi.utils.parsing import string_to_boolean

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.commtrack.util import get_supply_point_and_location
from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    PROFILE_SLUG,
)
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.user_importer.exceptions import UserUploadError
from corehq.apps.user_importer.helpers import spec_value_to_boolean_or_none
from corehq.apps.user_importer.validation import (
    get_user_import_validators,
    is_password,
)
from corehq.apps.users.account_confirmation import (
    send_account_confirmation_if_necessary,
)
from corehq.apps.users.models import (
    CommCareUser,
    CouchUser,
    Invitation,
    SQLUserRole,
    InvitationStatus
)
from corehq.apps.users.util import normalize_username, log_user_role_update
from corehq.const import USER_CHANGE_VIA_BULK_IMPORTER
from corehq.toggles import DOMAIN_PERMISSIONS_MIRROR

required_headers = set(['username'])
web_required_headers = set(['username', 'role'])
allowed_headers = set([
    'data', 'email', 'group', 'language', 'name', 'password', 'phone-number',
    'uncategorized_data', 'user_id', 'is_active', 'is_account_confirmed', 'send_confirmation_email',
    'location_code', 'role', 'user_profile',
    'User IMEIs (read only)', 'registered_on (read only)', 'last_submission (read only)',
    'last_sync (read only)', 'web_user', 'remove_web_user', 'remove', 'last_access_date (read only)',
    'last_login (read only)', 'last_name', 'status', 'first_name',
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

    def save_all(self):
        Group.bulk_save(self.groups)


def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, str):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")


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
            log['errors'].append('Your spreadsheet has multiple groups called "%s" and only the first was processed' % group_name)
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
    'roles_by_name', 'profiles_by_name', 'group_memoizer'
])


def create_or_update_web_user_invite(email, domain, role_qualified_id, upload_user, location_id, send_email=True):
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


def get_domain_info(domain, upload_domain, user_specs, domain_info_by_domain, upload_user=None, group_memoizer=None, is_web_upload=False):
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
        roles_by_name = {role.name: role.get_qualified_id() for role in SQLUserRole.objects.get_by_domain(domain)}
        definition = CustomDataFieldsDefinition.get(domain, UserFieldsView.field_type)
        if definition:
            profiles_by_name = {
                profile.name: profile
                for profile in definition.get_profiles()
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


def create_or_update_users_and_groups(upload_domain, user_specs, upload_user, group_memoizer=None, update_progress=None):
    domain_info_by_domain = {}

    ret = {"errors": [], "rows": []}

    current = 0

    try:
        for row in user_specs:
            if update_progress:
                update_progress(current)
                current += 1
            log_user_create = False
            log_role_update = False

            username = row.get('username')
            domain = row.get('domain') or upload_domain
            username = normalize_username(str(username), domain) if username else None
            status_row = {
                'username': username,
                'row': row,
            }

            try:
                domain_info = get_domain_info(domain, upload_domain, user_specs, domain_info_by_domain,
                                              group_memoizer)

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
            phone_number = row.get('phone-number')
            uncategorized_data = row.get('uncategorized_data', {})
            user_id = row.get('user_id')
            location_codes = row.get('location_code', []) if 'location_code' in row else None
            location_codes = format_location_codes(location_codes)
            role = row.get('role', None)
            profile = row.get('user_profile', None)
            web_user = row.get('web_user')

            try:
                password = str(password) if password else None

                is_active = spec_value_to_boolean_or_none(row, 'is_active')
                is_account_confirmed = spec_value_to_boolean_or_none(row, 'is_account_confirmed')
                send_account_confirmation_email = spec_value_to_boolean_or_none(row, 'send_confirmation_email')
                remove_web_user = spec_value_to_boolean_or_none(row, 'remove_web_user')

                if user_id:
                    user = CommCareUser.get_by_user_id(user_id, domain)
                    if not user:
                        raise UserUploadError(_(
                            "User with ID '{user_id}' not found"
                        ).format(user_id=user_id, domain=domain))
                    check_changing_username(user, username)

                    # note: explicitly not including "None" here because that's the default value if not set.
                    # False means it was set explicitly to that value
                    if is_account_confirmed is False and not web_user:
                        raise UserUploadError(_(
                            "You can only set 'Is Account Confirmed' to 'False' on a new User."
                        ))

                    if is_password(password):
                        user.set_password(password)
                        # overwrite password in results so we do not save it to the db
                        status_row['row']['password'] = 'REDACTED'
                    status_row['flag'] = 'updated'
                else:
                    kwargs = {}
                    if is_account_confirmed is not None and not web_user:
                        kwargs['is_account_confirmed'] = is_account_confirmed
                    user = CommCareUser.create(domain, username, password, created_by=upload_user,
                                               created_via=USER_CHANGE_VIA_BULK_IMPORTER, commit=False, **kwargs)
                    log_user_create = True
                    status_row['flag'] = 'created'

                if phone_number:
                    user.add_phone_number(_fmt_phone(phone_number), default=True)
                if name:
                    user.set_full_name(str(name))

                # Add in existing data. Don't use metadata - we don't want to add profile-controlled fields.
                for key, value in user.user_data.items():
                    if key not in data:
                        data[key] = value
                if profile:
                    profile_obj = domain_info.profiles_by_name[profile]
                    data[PROFILE_SLUG] = profile_obj.id
                    for key in profile_obj.fields.keys():
                        user.pop_metadata(key)
                try:
                    user.update_metadata(data)
                except ValueError as e:
                    raise UserUploadError(str(e))
                if uncategorized_data:
                    user.update_metadata(uncategorized_data)

                # Clear blank user data so that it can be purged by remove_unused_custom_fields_from_users_task
                for key in dict(data, **uncategorized_data):
                    value = user.metadata[key]
                    if value is None or value == '':
                        user.pop_metadata(key)

                if language:
                    user.language = language
                if email:
                    user.email = email.lower()
                if is_active is not None:
                    user.is_active = is_active

                if domain_info.can_assign_locations and location_codes is not None:
                    # Do this here so that we validate the location code before we
                    # save any other information to the user, this way either all of
                    # the user's information is updated, or none of it

                    # Do not update location info if the column is not included at all
                    location_ids = find_location_id(location_codes, domain_info.location_cache)
                    locations_updated, primary_loc_removed = check_modified_user_loc(location_ids,
                                                                                     user.location_id,
                                                                                     user.assigned_location_ids)
                    if primary_loc_removed:
                        user.unset_location(commit=False)
                    if locations_updated:
                        user.reset_locations(location_ids, commit=False)

                if role:
                    role_qualified_id = domain_info.roles_by_name[role]
                    user_current_role = user.get_role(domain=domain)
                    log_role_update = not (user_current_role
                                        and user_current_role.get_qualified_id() == role_qualified_id)
                    if log_role_update:
                        user.set_role(domain, role_qualified_id)

                if web_user:
                    user.update_metadata({'login_as_user': web_user})

                user.save()
                if log_user_create:
                    user.log_user_create(upload_user, USER_CHANGE_VIA_BULK_IMPORTER)
                if log_role_update:
                    log_user_role_update(domain, user, upload_user, USER_CHANGE_VIA_BULK_IMPORTER)
                if web_user:
                    check_can_upload_web_users(upload_user)
                    current_user = CouchUser.get_by_username(web_user)
                    if remove_web_user:
                        remove_web_user_from_domain(domain, current_user, username, upload_user)
                    else:
                        check_user_role(username, role)
                        if not current_user and is_account_confirmed:
                            raise UserUploadError(_(
                                "You can only set 'Is Account Confirmed' to 'True' on an existing Web User. {web_user} is a new username.").format(web_user=web_user)
                            )
                        if current_user and not current_user.is_member_of(domain) and is_account_confirmed:
                            current_user.add_as_web_user(domain, role=role_qualified_id, location_id=user.location_id)

                        elif not current_user or not current_user.is_member_of(domain):
                            create_or_update_web_user_invite(web_user, domain, role_qualified_id, upload_user, user.location_id,
                                                             send_email=send_account_confirmation_email)

                        elif current_user.is_member_of(domain):
                            # edit existing user in the domain
                            current_user.set_role(domain, role_qualified_id)
                            if location_codes is not None:
                                if user.location_id:
                                    current_user.set_location(domain, user.location_id)
                                else:
                                    current_user.unset_location(domain)
                            current_user.save()

                if send_account_confirmation_email and not web_user:
                    send_account_confirmation_if_necessary(user)

                if is_password(password):
                    # Without this line, digest auth doesn't work.
                    # With this line, digest auth works.
                    # Other than that, I'm not sure what's going on
                    # Passing use_primary_db=True because of https://dimagi-dev.atlassian.net/browse/ICDS-465
                    user.get_django_user(use_primary_db=True).check_password(password)

                for group in domain_info.group_memoizer.by_user_id(user.user_id):
                    if group.name not in group_names:
                        group.remove_user(user)

                for group_name in group_names:
                    domain_info.group_memoizer.by_name(group_name).add_user(user, save=False)

            except (UserUploadError, CouchUser.Inconsistent) as e:
                status_row['flag'] = str(e)

            ret["rows"].append(status_row)
    finally:
        try:
            for domain_info in domain_info_by_domain.values():
                domain_info.group_memoizer.save_all()
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

    return ret


def create_or_update_web_users(upload_domain, user_specs, upload_user, update_progress=None):
    domain_info_by_domain = {}

    ret = {"errors": [], "rows": []}
    current = 0

    for row in user_specs:
        if update_progress:
            update_progress(current)
            current += 1
        role_updated = False

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
            check_can_upload_web_users(upload_user)

            user = CouchUser.get_by_username(username, strict=True)
            if user:
                check_changing_username(user, username)
                if remove:
                    remove_web_user_from_domain(domain, user, username, upload_user, is_web_upload=True)
                else:
                    membership = user.get_domain_membership(domain)
                    if membership:
                        modify_existing_user_in_domain(domain, domain_info, location_codes, membership,
                                                       role_qualified_id, upload_user, user)
                    else:
                        create_or_update_web_user_invite(username, domain, role_qualified_id, upload_user,
                                                         user.location_id)
                status_row['flag'] = 'updated'

            else:
                if remove:
                    remove_invited_web_user(domain, username)
                    status_row['flag'] = 'updated'
                else:
                    if status == "Invited":
                        try:
                            invitation = Invitation.objects.get(domain=domain, email=username)
                        except Invitation.DoesNotExist:
                            raise UserUploadError(_("You can only set 'Status' to 'Invited' on a pending Web User."
                                                    " {web_user} is not yet invited.").format(web_user=username))
                        if invitation.email_status == InvitationStatus.BOUNCED and invitation.email == username:
                            raise UserUploadError(_("The email has bounced for this user's invite. Please try "
                                                    "again with a different username").format(web_user=username))
                    user_invite_loc_id = None
                    if domain_info.can_assign_locations and location_codes is not None:
                        # set invite location to first item in location_codes
                        if len(location_codes) > 0:
                            user_invite_loc = get_location_from_site_code(location_codes[0], domain_info.location_cache)
                            user_invite_loc_id = user_invite_loc.location_id
                    create_or_update_web_user_invite(username, domain, role_qualified_id, upload_user,
                                                     user_invite_loc_id)
                    status_row['flag'] = 'invited'

        except (UserUploadError, CouchUser.Inconsistent) as e:
            status_row['flag'] = str(e)

        ret["rows"].append(status_row)

    return ret


def modify_existing_user_in_domain(domain, domain_info, location_codes, membership, role_qualified_id,
                                   upload_user, current_user, max_tries=3):
    if domain_info.can_assign_locations and location_codes is not None:
        location_ids = find_location_id(location_codes, domain_info.location_cache)
        locations_updated, primary_loc_removed = check_modified_user_loc(location_ids,
                                                                         membership.location_id,
                                                                         membership.assigned_location_ids)
        if primary_loc_removed:
            current_user.unset_location(domain, commit=False)
        if locations_updated:
            current_user.reset_locations(domain, location_ids, commit=False)
    user_current_role = current_user.get_role(domain=domain)
    role_updated = not (user_current_role
                        and user_current_role.get_qualified_id() == role_qualified_id)
    if role_updated:
        current_user.set_role(domain, role_qualified_id)
        log_user_role_update(domain, current_user, upload_user,
                             USER_CHANGE_VIA_BULK_IMPORTER)
    try:
        current_user.save()
    except ResourceConflict:
        notify_exception(None, message="ResouceConflict during web user import",
                         details={'domain': domain, 'username': current_user.username})
        if max_tries > 0:
            current_user.clear_quickcache_for_user()
            updated_user = CouchUser.get_by_username(current_user.username, strict=True)
            modify_existing_user_in_domain(domain, domain_info, location_codes, membership, role_qualified_id,
                                           upload_user, updated_user, max_tries=max_tries - 1)
        else:
            raise


def check_user_role(username, role):
    if not role:
        raise UserUploadError(_(
            "You cannot upload a web user without a role. {username} does not have "
            "a role").format(username=username))


def check_can_upload_web_users(upload_user):
    if not upload_user.can_edit_web_users():
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


def remove_web_user_from_domain(domain, user, username, upload_user, is_web_upload=False):
    if not user or not user.is_member_of(domain):
        if is_web_upload:
            remove_invited_web_user(domain, username)
        else:
            raise UserUploadError(_("You cannot remove a web user that is not a member of this project."
                                    " {web_user} is not a member.").format(web_user=user))
    elif username == upload_user.username:
        raise UserUploadError(_("You cannot remove a yourself from a domain via bulk upload"))
    else:
        user.delete_domain_membership(domain)
        user.save()
