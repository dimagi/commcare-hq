from StringIO import StringIO
import logging
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import ugettext as _
from corehq.util.workbook_json.excel import flatten_json, json_to_headers, \
    alphanumeric_sort_key
from dimagi.utils.parsing import string_to_boolean

from couchdbkit.exceptions import (
    BulkSaveError,
    MultipleResultsFound,
    ResourceNotFound,
)
from couchexport.writers import Excel2007ExportWriter
from soil import DownloadBase

from corehq import privileges
from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.commtrack.util import submit_mapping_case_block, get_supply_point_and_location
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.groups.models import Group
from corehq.apps.domain.forms import clean_password
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_all_commcare_users_by_domain,
    get_user_docs_by_username,
)
from corehq.apps.users.models import UserRole

from .forms import get_mobile_worker_max_username_length
from .models import CommCareUser, CouchUser
from .util import normalize_username, raw_username


class UserUploadError(Exception):
    pass


required_headers = set(['username'])
allowed_headers = set([
    'data', 'email', 'group', 'language', 'name', 'password', 'phone-number',
    'uncategorized_data', 'user_id', 'is_active', 'location_code', 'role', 'User IMEIs (read only)',
]) | required_headers
old_headers = {
    # 'old_header_name': 'new_header_name'
    'location-sms-code': 'location_code'
}


def check_headers(user_specs):
    messages = []
    headers = set(user_specs.fieldnames)

    # Backwards warnings
    for (old_name, new_name) in old_headers.iteritems():
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


def check_duplicate_usernames(user_specs):
    usernames = set()
    duplicated_usernames = set()

    for row in user_specs:
        username = row.get('username')
        if username and username in usernames:
            duplicated_usernames.add(username)
        usernames.add(username)

    if duplicated_usernames:
        raise UserUploadError(_("The following usernames have duplicate entries in "
            "your file: " + ', '.join(duplicated_usernames)))


def check_existing_usernames(user_specs, domain):
    usernames_without_ids = set()
    invalid_usernames = set()

    for row in user_specs:
        username = row.get('username')
        user_id = row.get('user_id')
        if username and user_id:
            continue
        try:
            usernames_without_ids.add(normalize_username(username, domain))
        except ValidationError:
            invalid_usernames.add(username)

    if invalid_usernames:
        raise UserUploadError(_('The following usernames are invalid: ' + ', '.join(invalid_usernames)))

    existing_usernames = [u.get('username') for u in get_user_docs_by_username(usernames_without_ids)]

    if existing_usernames:
        raise UserUploadError(_("The following usernames already exist and must "
            "have an id specified to be updated: " + ', '.join(existing_usernames)))


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

    def load_all(self):
        for group in Group.by_domain(self.domain):
            self.add_group(group)

    def add_group(self, new_group):
        # todo
        # this has the possibility of missing two rows one with id one with name
        # that actually refer to the same group
        # and overwriting one with the other
        assert new_group.name
        if new_group.get_id:
            self.groups_by_id[new_group.get_id] = new_group
        self.groups_by_name[new_group.name] = new_group
        self.groups.add(new_group)

    def by_name(self, group_name):
        if not self.groups_by_name.has_key(group_name):
            group = Group.by_name(self.domain, group_name)
            if not group:
                self.groups_by_name[group_name] = None
                return None
            self.add_group(group)
        return self.groups_by_name[group_name]

    def get(self, group_id):
        if not self.groups_by_id.has_key(group_id):
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
    if phone_number and not isinstance(phone_number, basestring):
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
        return super(SiteCodeToLocationCache, self).__init__(domain)

    def lookup(self, site_code):
        """
        Note that this can raise SQLLocation.DoesNotExist if the location with the
        given site code is not found.
        """
        return SQLLocation.objects.get(
            domain=self.domain,
            site_code=site_code
        )


class LocationIdToSiteCodeCache(BulkCacheBase):

    def lookup(self, location_id):
        return SQLLocation.objects.get(
            domain=self.domain,  # this is only for safety
            location_id=location_id
        ).site_code


def create_or_update_groups(domain, group_specs, log):
    group_memoizer = GroupMemoizer(domain)
    group_memoizer.load_all()
    group_names = set()
    for row in group_specs:
        group_id = row.get('id')
        group_name = unicode(row.get('name') or '')
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
    return group_memoizer


def get_location_from_site_code(site_code, location_cache):
    if isinstance(site_code, basestring):
        site_code = site_code.lower()
    elif isinstance(site_code, (int, long)):
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


def is_password(password):
    if not password:
        return False
    for c in password:
        if c != "*":
            return True
    return False


def users_with_duplicate_passwords(rows):
    password_dict = dict()

    for row in rows:
        username = row.get('username')
        password = unicode(row.get('password'))
        if not is_password(password):
            continue

        if password_dict.get(password):
            password_dict[password].add(username)
        else:
            password_dict[password] = {username}

    ret = set()

    for usernames in password_dict.values():
        if len(usernames) > 1:
            ret = ret.union(usernames)

    return ret


def create_or_update_users_and_groups(domain, user_specs, group_specs, task=None):
    from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
    custom_data_validator = UserFieldsView.get_validator(domain)
    ret = {"errors": [], "rows": []}
    total = len(user_specs) + len(group_specs)

    def _set_progress(progress):
        if task is not None:
            DownloadBase.set_progress(task, progress, total)

    group_memoizer = create_or_update_groups(domain, group_specs, log=ret)
    current = len(group_specs)

    usernames = set()
    user_ids = set()
    allowed_groups = set(group_memoizer.groups)
    allowed_group_names = [group.name for group in allowed_groups]
    allowed_roles = UserRole.by_domain(domain)
    roles_by_name = {role.name: role for role in allowed_roles}
    can_assign_locations = domain_has_privilege(domain, privileges.LOCATIONS)
    # ToDo: We need more speccing on what/how locations can be assigned if location-restrictions is enabled
    #       For now, don't support bulk assigning if location-restrictions are enabled
    can_assign_locations = can_assign_locations and not toggles.RESTRICT_WEB_USERS_BY_LOCATION.enabled(domain)
    if can_assign_locations:
        location_cache = SiteCodeToLocationCache(domain)
    project = Domain.get_by_name(domain)
    usernames_with_dupe_passwords = users_with_duplicate_passwords(user_specs)

    try:
        for row in user_specs:
            _set_progress(current)
            current += 1

            data = row.get('data')
            email = row.get('email')
            group_names = map(unicode, row.get('group') or [])
            language = row.get('language')
            name = row.get('name')
            password = row.get('password')
            phone_number = row.get('phone-number')
            uncategorized_data = row.get('uncategorized_data')
            user_id = row.get('user_id')
            username = row.get('username')
            location_codes = row.get('location_code') or []
            if location_codes and not isinstance(location_codes, list):
                location_codes = [location_codes]
            # ignore empty
            location_codes = [code for code in location_codes if code]
            role = row.get('role', '')

            if password:
                password = unicode(password)
            try:
                username = normalize_username(str(username), domain)
            except TypeError:
                username = None
            except ValidationError:
                ret['rows'].append({
                    'username': username,
                    'row': row,
                    'flag': _('username cannot contain spaces or symbols'),
                })
                continue
            status_row = {
                'username': raw_username(username) if username else None,
                'row': row,
            }

            is_active = row.get('is_active')
            if isinstance(is_active, basestring):
                try:
                    is_active = string_to_boolean(is_active) if is_active else None
                except ValueError:
                    ret['rows'].append({
                        'username': username,
                        'row': row,
                        'flag': _("'is_active' column can only contain 'true' or 'false'"),
                    })
                    continue

            if username in usernames or user_id in user_ids:
                status_row['flag'] = 'repeat'
            elif not username and not user_id:
                status_row['flag'] = 'missing-data'
            else:
                try:
                    if username:
                        usernames.add(username)
                    if user_id:
                        user_ids.add(user_id)
                    if user_id:
                        user = CommCareUser.get_by_user_id(user_id, domain)
                    else:
                        user = CommCareUser.get_by_username(username)

                    if project.strong_mobile_passwords and is_password(password):
                        if raw_username(username) in usernames_with_dupe_passwords:
                            raise UserUploadError(_("Provide a unique password for each mobile worker"))

                        try:
                            clean_password(password)
                        except forms.ValidationError:
                            if settings.ENABLE_DRACONIAN_SECURITY_FEATURES:
                                msg = _("Mobile Worker passwords must be 8 "
                                    "characters long with at least 1 capital "
                                    "letter, 1 special character and 1 number")
                            else:
                                msg = _("Please provide a stronger password")
                            raise UserUploadError(msg)

                    if user:
                        if user.domain != domain:
                            raise UserUploadError(_(
                                'User with username %(username)r is '
                                'somehow in domain %(domain)r'
                            ) % {'username': user.username, 'domain': user.domain})
                        if username and user.username != username:
                            user.change_username(username)
                        if is_password(password):
                            user.set_password(password)
                        status_row['flag'] = 'updated'
                    else:
                        max_username_length = get_mobile_worker_max_username_length(domain)
                        if len(raw_username(username)) > max_username_length:
                            ret['rows'].append({
                                'username': username,
                                'row': row,
                                'flag': _("username cannot contain greater than %d characters" %
                                          max_username_length)
                            })
                            continue
                        if not is_password(password):
                            raise UserUploadError(_("Cannot create a new user with a blank password"))
                        user = CommCareUser.create(domain, username, password, commit=False)
                        status_row['flag'] = 'created'
                    if phone_number:
                        user.add_phone_number(_fmt_phone(phone_number), default=True)
                    if name:
                        user.set_full_name(unicode(name))
                    if data:
                        error = custom_data_validator(data)
                        if error:
                            raise UserUploadError(error)
                        user.user_data.update(data)
                    if uncategorized_data:
                        user.user_data.update(uncategorized_data)
                    if language:
                        user.language = language
                    if email:
                        try:
                            validate_email(email)
                        except ValidationError:
                            raise UserUploadError(_("User has an invalid email address"))

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

                    if role:
                        if role in roles_by_name:
                            user.set_role(domain, roles_by_name[role].get_qualified_id())
                        else:
                            raise UserUploadError(_(
                                "Role '%s' does not exist"
                            ) % role)

                    # following blocks require user doc id, so it needs to be saved if new user
                    user.save()
                    if can_assign_locations:
                        if (user.location_id and not location_ids or
                           user.location_id not in location_ids):
                            user.unset_location()
                        if set(user.assigned_location_ids) != set(location_ids):
                            user.reset_locations(location_ids)

                    if is_password(password):
                        # Without this line, digest auth doesn't work.
                        # With this line, digest auth works.
                        # Other than that, I'm not sure what's going on
                        user.get_django_user().check_password(password)

                    for group_id in Group.by_user(user, wrap=False):
                        group = group_memoizer.get(group_id)
                        if group.name not in group_names:
                            group.remove_user(user, save=False)

                    for group_name in group_names:
                        if group_name not in allowed_group_names:
                            raise UserUploadError(_(
                                "Can't add to group '%s' "
                                "(try adding it to your spreadsheet)"
                            ) % group_name)
                        group_memoizer.by_name(group_name).add_user(user, save=False)

                except (UserUploadError, CouchUser.Inconsistent) as e:
                    status_row['flag'] = unicode(e)

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

    _set_progress(total)
    return ret


class GroupNameError(Exception):

    def __init__(self, blank_groups):
        self.blank_groups = blank_groups

    @property
    def message(self):
        return "The following group ids have a blank name: %s." % (
            ', '.join([group.get_id for group in self.blank_groups])
        )


def build_data_headers(keys, header_prefix='data'):
    return json_to_headers(
        {header_prefix: {key: None for key in keys}}
    )


def parse_users(group_memoizer, domain, user_data_model, location_cache):

    def _get_group_names(user):
        return sorted(map(
            lambda id: group_memoizer.get(id).name,
            Group.by_user(user, wrap=False)
        ), key=alphanumeric_sort_key)

    def _get_devices(user):
        """
        Returns a comma-separated list of IMEI numbers of the user's devices, sorted with most-recently-used first
        """
        return ', '.join([device.device_id for device in sorted(
            user.devices, key=lambda d: d.last_used, reverse=True
        )])

    def _make_user_dict(user, group_names, location_cache):
        model_data, uncategorized_data = (
            user_data_model.get_model_and_uncategorized(user.user_data)
        )
        role = user.get_role(domain)
        location_codes = []
        try:
            location_codes.append(location_cache.get(user.location_id))
        except SQLLocation.DoesNotExist:
            pass
        for location_id in user.assigned_location_ids:
            # skip if primary location_id, as it is already added to the start of list above
            if location_id != user.location_id:
                try:
                    location_codes.append(location_cache.get(location_id))
                except SQLLocation.DoesNotExist:
                    pass
        return {
            'data': model_data,
            'uncategorized_data': uncategorized_data,
            'group': group_names,
            'name': user.full_name,
            'password': "********",  # dummy display string for passwords
            'phone-number': user.phone_number,
            'email': user.email,
            'username': user.raw_username,
            'language': user.language,
            'user_id': user._id,
            'is_active': str(user.is_active),
            'User IMEIs (read only)': _get_devices(user),
            'location_code': location_codes,
            'role': role.name if role else '',
        }

    unrecognized_user_data_keys = set()
    user_groups_length = 0
    max_location_length = 0
    user_dicts = []
    for user in get_all_commcare_users_by_domain(domain):
        group_names = _get_group_names(user)
        user_dict = _make_user_dict(user, group_names, location_cache)
        user_dicts.append(user_dict)
        unrecognized_user_data_keys.update(user_dict['uncategorized_data'].keys())
        user_groups_length = max(user_groups_length, len(group_names))
        max_location_length = max(max_location_length, len(user_dict["location_code"]))

    user_headers = [
        'username', 'password', 'name', 'phone-number', 'email',
        'language', 'role', 'user_id', 'is_active', 'User IMEIs (read only)',
    ]

    user_data_fields = [f.slug for f in user_data_model.get_fields(include_system=False)]
    user_headers.extend(build_data_headers(user_data_fields))
    user_headers.extend(build_data_headers(
        unrecognized_user_data_keys,
        header_prefix='uncategorized_data'
    ))
    user_headers.extend(json_to_headers(
        {'group': range(1, user_groups_length + 1)}
    ))
    if domain_has_privilege(domain, privileges.LOCATIONS):
        user_headers.extend(json_to_headers(
            {'location_code': range(1, max_location_length + 1)}
        ))

    def _user_rows():
        for user_dict in user_dicts:
            row = dict(flatten_json(user_dict))
            yield [row.get(header) or '' for header in user_headers]
    return user_headers, _user_rows()


def parse_groups(groups):
    def _make_group_dict(group):
        return {
            'id': group.get_id,
            'name': group.name,
            'case-sharing': group.case_sharing,
            'reporting': group.reporting,
            'data': group.metadata,
        }

    group_data_keys = set()
    group_dicts = []
    sorted_groups = sorted(
        groups,
        key=lambda group: alphanumeric_sort_key(group.name)
    )
    for group in sorted_groups:
        group_dicts.append(_make_group_dict(group))
        group_data_keys.update(group.metadata.keys() if group.metadata else [])

    group_headers = ['id', 'name', 'case-sharing?', 'reporting?']
    group_headers.extend(build_data_headers(group_data_keys))

    def _get_group_rows():
        for group_dict in group_dicts:
            row = dict(flatten_json(group_dict))
            yield [row.get(header) or '' for header in group_headers]
    return group_headers, _get_group_rows()


def dump_users_and_groups(response, domain):
    from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView

    def _load_memoizer(domain):
        group_memoizer = GroupMemoizer(domain=domain)
        # load groups manually instead of calling group_memoizer.load_all()
        # so that we can detect blank groups
        blank_groups = set()
        for group in Group.by_domain(domain):
            if group.name:
                group_memoizer.add_group(group)
            else:
                blank_groups.add(group)
        if blank_groups:
            raise GroupNameError(blank_groups=blank_groups)

        return group_memoizer

    export_file = StringIO()
    writer = Excel2007ExportWriter()
    group_memoizer = _load_memoizer(domain)
    location_cache = LocationIdToSiteCodeCache(domain)

    user_data_model = CustomDataFieldsDefinition.get_or_create(
        domain,
        UserFieldsView.field_type
    )

    user_headers, user_rows = parse_users(
        group_memoizer,
        domain,
        user_data_model,
        location_cache
    )

    group_headers, group_rows = parse_groups(group_memoizer.groups)
    headers = [
        ('users', [user_headers]),
        ('groups', [group_headers]),
    ]
    rows = [
        ('users', user_rows),
        ('groups', group_rows),
    ]

    writer.open(
        header_table=headers,
        file=export_file,
    )
    writer.write(rows)
    writer.close()
    response.write(export_file.getvalue())
