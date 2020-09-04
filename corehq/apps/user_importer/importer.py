import logging
from collections import defaultdict, namedtuple
from datetime import datetime

from django.db import DEFAULT_DB_ALIAS
from django.utils.translation import ugettext as _

from couchdbkit.exceptions import (
    BulkSaveError,
    MultipleResultsFound,
    ResourceNotFound,
)

from dimagi.utils.parsing import string_to_boolean

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.commtrack.util import get_supply_point_and_location
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
    UserRole,
)
from corehq.apps.users.util import normalize_username
from corehq.const import USER_CHANGE_VIA_BULK_IMPORTER

required_headers = set(['username'])
allowed_headers = set([
    'data', 'email', 'group', 'language', 'name', 'password', 'phone-number',
    'uncategorized_data', 'user_id', 'is_active', 'is_account_confirmed', 'send_confirmation_email',
    'location_code', 'role',
    'User IMEIs (read only)', 'registered_on (read only)', 'last_submission (read only)',
    'last_sync (read only)', 'web_user', 'remove_web_user', 'domain'
]) | required_headers
old_headers = {
    # 'old_header_name': 'new_header_name'
    'location-sms-code': 'location_code'
}


def check_headers(user_specs):
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

    illegal_headers = headers - allowed_headers
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
    'roles_by_name', 'group_memoizer'
])


def create_or_update_users_and_groups(upload_domain, user_specs, upload_user, group_memoizer=None, update_progress=None):
    domain_info_by_domain = {}

    def _get_domain_info(domain):
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
        allowed_group_names = [group.name for group in domain_group_memoizer.groups]
        roles_by_name = {role.name: role for role in UserRole.by_domain(domain)}
        domain_user_specs = [spec for spec in user_specs if spec.get('domain', upload_domain) == domain]
        validators = get_user_import_validators(
            domain_obj,
            domain_user_specs,
            allowed_group_names,
            list(roles_by_name),
            upload_domain
        )

        domain_info = DomainInfo(
            validators,
            can_assign_locations,
            location_cache,
            roles_by_name,
            domain_group_memoizer
        )
        domain_info_by_domain[domain] = domain_info
        return domain_info

    ret = {"errors": [], "rows": []}

    current = 0

    try:
        for row in user_specs:
            if update_progress:
                update_progress(current)
                current += 1

            username = row.get('username')
            domain = row.get('domain') or upload_domain
            username = normalize_username(str(username), domain) if username else None
            status_row = {
                'username': username,
                'row': row,
            }

            domain_info = _get_domain_info(domain)

            try:
                for validator in domain_info.validators:
                    validator(row)
            except UserUploadError as e:
                status_row['flag'] = str(e)
                ret['rows'].append(status_row)
                continue

            data = row.get('data')
            email = row.get('email')
            group_names = list(map(str, row.get('group') or []))
            language = row.get('language')
            name = row.get('name')
            password = row.get('password')
            phone_number = row.get('phone-number')
            uncategorized_data = row.get('uncategorized_data')
            user_id = row.get('user_id')
            location_codes = row.get('location_code') or []
            if location_codes and not isinstance(location_codes, list):
                location_codes = [location_codes]
            # ignore empty
            location_codes = [code for code in location_codes if code]
            role = row.get('role', None)
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

                    if username and user.username != username:
                        raise UserUploadError(_(
                            'Changing usernames is not supported: %(username)r to %(new_username)r'
                        ) % {'username': user.username, 'new_username': username})

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
                    status_row['flag'] = 'created'

                if phone_number:
                    user.add_phone_number(_fmt_phone(phone_number), default=True)
                if name:
                    user.set_full_name(str(name))
                if data:
                    user.user_data.update(data)
                if uncategorized_data:
                    user.user_data.update(uncategorized_data)
                if language:
                    user.language = language
                if email:
                    user.email = email.lower()
                if is_active is not None:
                    user.is_active = is_active

                if domain_info.can_assign_locations:
                    # Do this here so that we validate the location code before we
                    # save any other information to the user, this way either all of
                    # the user's information is updated, or none of it
                    location_ids = []
                    for code in location_codes:
                        loc = get_location_from_site_code(code, domain_info.location_cache)
                        location_ids.append(loc.location_id)

                    locations_updated = set(user.assigned_location_ids) != set(location_ids)
                    primary_location_removed = (user.location_id and not location_ids or
                                                user.location_id not in location_ids)

                    if primary_location_removed:
                        user.unset_location(commit=False)
                    if locations_updated:
                        user.reset_locations(location_ids, commit=False)

                if role:
                    role_qualified_id = domain_info.roles_by_name[role].get_qualified_id()
                    user.set_role(domain, role_qualified_id)

                if web_user:
                    user.user_data.update({'login_as_user': web_user})

                user.save()

                if web_user:
                    if not upload_user.can_edit_web_users():
                        raise UserUploadError(_(
                            "Only users with the edit web users permission can upload web users"
                        ))
                    current_user = CouchUser.get_by_username(web_user)
                    if remove_web_user:
                        if not current_user or not current_user.is_member_of(domain):
                            raise UserUploadError(_(
                                "You cannot remove a web user that is not a member of this project. {web_user} is not a member.").format(web_user=web_user)
                            )
                        else:
                            current_user.delete_domain_membership(domain)
                            current_user.save()
                    else:
                        if not role:
                            raise UserUploadError(_(
                                "You cannot upload a web user without a role. {web_user} does not have a role").format(web_user=web_user)
                            )
                        if not current_user and is_account_confirmed:
                            raise UserUploadError(_(
                                "You can only set 'Is Account Confirmed' to 'True' on an existing Web User. {web_user} is a new username.").format(web_user=web_user)
                            )
                        if current_user and not current_user.is_member_of(domain) and is_account_confirmed:
                            current_user.add_as_web_user(domain, role=role_qualified_id, location_id=user.location_id)
                        elif not current_user or not current_user.is_member_of(domain):
                            invite_data = {
                                'email': web_user,
                                'invited_by': upload_user.user_id,
                                'invited_on': datetime.utcnow(),
                                'domain': domain,
                                'role': role_qualified_id,
                                'supply_point': user.location_id
                            }
                            invite = Invitation(**invite_data)
                            invite.save()
                            if send_account_confirmation_email:
                                invite.send_activation_email()

                        elif current_user.is_member_of(domain):
                            # edit existing user in the domain
                            current_user.set_role(domain, role_qualified_id)
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
