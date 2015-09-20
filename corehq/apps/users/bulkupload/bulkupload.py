from __future__ import absolute_import
from StringIO import StringIO

from django.utils.translation import ugettext as _

from .group_memoizer import GroupMemoizer

from corehq.apps.users.bulkupload.bulk_cache import LocationIdToSiteCodeCache
from corehq.apps.users.exceptions import UserUploadError
from corehq.util.spreadsheets.excel import flatten_json, json_to_headers, \
    alphanumeric_sort_key
from couchexport.writers import Excel2007ExportWriter
from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.commtrack.util import submit_mapping_case_block
from corehq.apps.custom_data_fields import CustomDataFieldsDefinition
from corehq.apps.groups.models import Group
from corehq.apps.domain.models import Domain
from corehq.apps.users.dbaccessors.all_commcare_users import get_all_commcare_users_by_domain
from ..models import CommCareUser


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
    from ..views.mobile.custom_data_fields import UserFieldsView

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
