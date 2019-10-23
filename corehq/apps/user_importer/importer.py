import logging
from collections import defaultdict

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
from corehq.apps.user_importer.validation import (
    get_user_import_validators,
    is_password,
)
from corehq.apps.users.models import CommCareUser, CouchUser, UserRole
from corehq.apps.users.util import normalize_username, raw_username

required_headers = set(['username'])
allowed_headers = set([
    'data', 'email', 'group', 'language', 'name', 'password', 'phone-number',
    'uncategorized_data', 'user_id', 'is_active', 'location_code', 'role',
    'User IMEIs (read only)', 'registered_on (read only)',
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
        return SQLLocation.objects.using('default').get(
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


def create_or_update_users_and_groups(domain, user_specs, group_memoizer=None, update_progress=None):
    ret = {"errors": [], "rows": []}

    group_memoizer = group_memoizer or GroupMemoizer(domain)
    group_memoizer.load_all()

    current = 0

    can_assign_locations = domain_has_privilege(domain, privileges.LOCATIONS)
    if can_assign_locations:
        location_cache = SiteCodeToLocationCache(domain)

    domain_obj = Domain.get_by_name(domain)
    allowed_group_names = [group.name for group in group_memoizer.groups]
    roles_by_name = {role.name: role for role in UserRole.by_domain(domain)}
    validators = get_user_import_validators(domain_obj, user_specs, allowed_group_names, list(roles_by_name))
    try:
        for row in user_specs:
            if update_progress:
                update_progress(current)
                current += 1

            username = row.get('username')
            status_row = {
                'username': username,
                'row': row,
            }

            try:
                for validator in validators:
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
            role = row.get('role', '')

            try:
                username = normalize_username(str(username), domain) if username else None
                password = str(password) if password else None

                is_active = row.get('is_active') or None
                if is_active and isinstance(is_active, str):
                    is_active = string_to_boolean(is_active)

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

                    if is_password(password):
                        user.set_password(password)
                    status_row['flag'] = 'updated'
                else:
                    user = CommCareUser.create(domain, username, password, commit=False)
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

                if can_assign_locations:
                    # Do this here so that we validate the location code before we
                    # save any other information to the user, this way either all of
                    # the user's information is updated, or none of it
                    location_ids = []
                    for code in location_codes:
                        loc = get_location_from_site_code(code, location_cache)
                        location_ids.append(loc.location_id)

                    locations_updated = set(user.assigned_location_ids) != set(location_ids)
                    primary_location_removed = (user.location_id and not location_ids or
                                                user.location_id not in location_ids)

                    if primary_location_removed:
                        user.unset_location(commit=False)
                    if locations_updated:
                        user.reset_locations(location_ids, commit=False)

                if role:
                    user.set_role(domain, roles_by_name[role].get_qualified_id())

                user.save()

                if is_password(password):
                    # Without this line, digest auth doesn't work.
                    # With this line, digest auth works.
                    # Other than that, I'm not sure what's going on
                    # Passing use_primary_db=True because of https://dimagi-dev.atlassian.net/browse/ICDS-465
                    user.get_django_user(use_primary_db=True).check_password(password)

                for group in group_memoizer.by_user_id(user.user_id):
                    if group.name not in group_names:
                        group.remove_user(user)

                for group_name in group_names:
                    group_memoizer.by_name(group_name).add_user(user, save=False)

            except (UserUploadError, CouchUser.Inconsistent) as e:
                status_row['flag'] = str(e)

            ret["rows"].append(status_row)
    finally:
        try:
            group_memoizer.save_all()
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
