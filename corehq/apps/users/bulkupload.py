from StringIO import StringIO
import logging
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from corehq.util.spreadsheets.excel import flatten_json, json_to_headers, \
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
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.commtrack.util import get_supply_point, submit_mapping_case_block
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_commcare_users_by_domain

from .forms import CommCareAccountForm
from .models import CommCareUser, CouchUser
from .util import normalize_username, raw_username
from .views.mobile.custom_data_fields import UserFieldsView


class UserUploadError(Exception):
    pass


required_headers = set(['username'])
allowed_headers = set([
    'data', 'email', 'group', 'language', 'name', 'password', 'phone-number',
    'uncategorized_data', 'user_id', 'is_active', 'location-sms-code',
]) | required_headers


def check_headers(user_specs):
    headers = set(user_specs.fieldnames)

    illegal_headers = headers - allowed_headers
    missing_headers = required_headers - headers

    messages = []
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
        supply_point = get_supply_point(
            self.domain,
            site_code
        )['case']
        return supply_point


class SiteCodeToLocationCache(BulkCacheBase):
    def __init__(self, domain):
        self.non_admin_types = [
            loc_type.name for loc_type in Domain.get_by_name(domain).location_types
            if not loc_type.administrative
        ]
        return super(SiteCodeToLocationCache, self).__init__(domain)

    def lookup(self, site_code):
        return SQLLocation.objects.get(
            domain=self.domain,
            site_code=site_code
        ).couch_location


class LocationIdToSiteCodeCache(BulkCacheBase):
    def lookup(self, location_id):
        return SQLLocation.objects.get(
            domain=self.domain,  # this is only for safety
            location_id=location_id
        ).site_code


class UserLocMapping(object):
    def __init__(self, username, domain, location_cache):
        self.username = username
        self.domain = domain
        self.to_add = set()
        self.to_remove = set()
        self.location_cache = location_cache

    def get_supply_point_from_location(self, sms_code):
        return self.location_cache.get(sms_code)

    def save(self):
        """
        Calculate which locations need added or removed, then submit
        one caseblock to handle this
        """
        user = CommCareUser.get_by_username(self.username)
        if not user:
            raise UserUploadError(_('no username with {} found!'.format(self.username)))

        current_locations = user.locations
        current_location_codes = [loc.site_code for loc in current_locations]

        commit_list = {}
        messages = []

        def _add_loc(loc, clear=False):
            sp = self.get_supply_point_from_location(loc)
            if sp is None:
                messages.append(_(
                    "No supply point found for location '{}'. "
                    "Make sure the location type is not set to administrative only "
                    "and that the location has a valid sms code."
                ).format(loc or ''))
            else:
                commit_list.update(user.supply_point_index_mapping(sp, clear))

        for loc in self.to_add:
            if loc not in current_location_codes:
                _add_loc(loc)
        for loc in self.to_remove:
            if loc in current_location_codes:
                _add_loc(loc, clear=True)

        if commit_list:
            submit_mapping_case_block(user, commit_list)

        return messages


def create_or_update_locations(domain, location_specs, log):
    """
    This method should only be used when uploading multiple
    location per user situations. This is behind a feature
    flag and is not for normal use.

    It is special because it is creating delegate case
    submissions to give this location access.
    """
    sp_cache = SiteCodeToSupplyPointCache(domain)
    users = {}
    for row in location_specs:
        username = row.get('username')
        try:
            username = normalize_username(username, domain)
        except ValidationError:
            log['errors'].append(
                _("Username must be a valid email address: %s") % username
            )
        else:
            location_code = unicode(row.get('location-sms-code'))
            if username in users:
                user_mapping = users[username]
            else:
                user_mapping = UserLocMapping(username, domain, sp_cache)
                users[username] = user_mapping

            if row.get('remove') == 'y':
                user_mapping.to_remove.add(location_code)
            else:
                user_mapping.to_add.add(location_code)

    for username, mapping in users.iteritems():
        try:
            messages = mapping.save()
            log['errors'].extend(messages)
        except UserUploadError as e:
            log['errors'].append(
                _('Unable to update locations for {user} because {message}'.format(
                    user=username,
                    message=e
                ))
            )


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


def create_or_update_users_and_groups(domain, user_specs, group_specs, location_specs, task=None):
    custom_data_validator = UserFieldsView.get_validator(domain)
    ret = {"errors": [], "rows": []}
    total = len(user_specs) + len(group_specs) + len(location_specs)
    def _set_progress(progress):
        if task is not None:
            DownloadBase.set_progress(task, progress, total)

    group_memoizer = create_or_update_groups(domain, group_specs, log=ret)
    current = len(group_specs)

    usernames = set()
    user_ids = set()
    allowed_groups = set(group_memoizer.groups)
    allowed_group_names = [group.name for group in allowed_groups]
    can_access_locations = domain_has_privilege(domain, privileges.LOCATIONS)
    if can_access_locations:
        location_cache = SiteCodeToLocationCache(domain)
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
            location_code = row.get('location-sms-code', '')

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
                    is_active = string_to_boolean(is_active)
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

                    def is_password(password):
                        if not password:
                            return False
                        for c in password:
                            if c != "*":
                                return True
                        return False

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
                        if len(raw_username(username)) > CommCareAccountForm.max_len_username:
                            ret['rows'].append({
                                'username': username,
                                'row': row,
                                'flag': _("username cannot contain greater than %d characters" %
                                          CommCareAccountForm.max_len_username)
                            })
                            continue
                        if not is_password(password):
                            raise UserUploadError(_("Cannot create a new user with a blank password"))
                        user = CommCareUser.create(domain, username, password, commit=False)
                        status_row['flag'] = 'created'
                    if phone_number:
                        user.add_phone_number(_fmt_phone(phone_number), default=True)
                    if name:
                        user.set_full_name(name)
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
                        user.email = email
                    if is_active is not None:
                        user.is_active = is_active

                    user.save()
                    if can_access_locations and location_code:
                        loc = location_cache.get(location_code)
                        if user.location_id != loc._id:
                            # this triggers a second user save so
                            # we want to avoid doing it if it isn't
                            # needed
                            user.set_location(loc)
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

    if Domain.get_by_name(domain).supports_multiple_locations_per_user:
        create_or_update_locations(domain, location_specs, log=ret)
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


def get_location_rows(domain):
    users = CommCareUser.by_domain(domain)

    mappings = []
    for user in users:
        # this method is only called when exporting the
        # locaiton tab (so on domains with multiple
        # locations per user), so we are relying on
        # user.locations being a thing that is real
        # and working
        locations = user.locations
        for location in locations:
            mappings.append([
                user.raw_username,
                location.site_code,
                location.name
            ])

    return mappings


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

    def _make_user_dict(user, group_names, location_cache):
        model_data, uncategorized_data = (
            user_data_model.get_model_and_uncategorized(user.user_data)
        )
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
            'location-sms-code': location_cache.get(user.location_id),
        }

    user_data_keys = set()
    user_groups_length = 0
    user_dicts = []
    for user in get_all_commcare_users_by_domain(domain):
        group_names = _get_group_names(user)
        user_dicts.append(_make_user_dict(user, group_names, location_cache))
        user_data_keys.update(user.user_data.keys() if user.user_data else [])
        user_groups_length = max(user_groups_length, len(group_names))

    user_headers = [
        'username', 'password', 'name', 'phone-number', 'email',
        'language', 'user_id', 'is_active',
    ]
    if domain_has_privilege(domain, privileges.LOCATIONS):
        user_headers.append('location-sms-code')
    user_data_fields = [f.slug for f in user_data_model.fields]
    user_headers.extend(build_data_headers(user_data_fields))
    user_headers.extend(build_data_headers(
        user_data_keys.difference(set(user_data_fields)),
        header_prefix='uncategorized_data'
    ))
    user_headers.extend(json_to_headers(
        {'group': range(1, user_groups_length + 1)}
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

    domain_obj = Domain.get_by_name(domain)
    # This is only for domains using the multiple locations feature flag
    if domain_obj.commtrack_enabled and domain_obj.supports_multiple_locations_per_user:
        headers.append(
            ('locations', [['username', 'location-sms-code', 'location name (optional)']])
        )
        rows.append(
            ('locations', get_location_rows(domain))
        )

    writer.open(
        header_table=headers,
        file=export_file,
    )
    writer.write(rows)
    writer.close()
    response.write(export_file.getvalue())
