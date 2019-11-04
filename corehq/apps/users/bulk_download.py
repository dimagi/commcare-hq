import uuid

from django.conf import settings

from couchexport.writers import Excel2007ExportWriter
from soil import DownloadBase
from soil.util import expose_download, get_download_file_path

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.user_importer.importer import BulkCacheBase, GroupMemoizer
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_commcare_users_by_filters,
)
from corehq.util.workbook_json.excel import (
    alphanumeric_sort_key,
    flatten_json,
    json_to_headers,
)


class LocationIdToSiteCodeCache(BulkCacheBase):

    def lookup(self, location_id):
        return SQLLocation.objects.get(
            domain=self.domain,  # this is only for safety
            location_id=location_id
        ).site_code


def build_data_headers(keys, header_prefix='data'):
    return json_to_headers(
        {header_prefix: {key: None for key in keys}}
    )


def parse_users(group_memoizer, domain, user_data_model, location_cache, user_filters, task, total_count):

    def _get_group_names(user):
        return sorted([
            group_memoizer.get(id).name for id in Group.by_user_id(user.user_id, wrap=False)
        ], key=alphanumeric_sort_key)

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
            'registered_on (read only)': user.created_on.strftime('%Y-%m-%d %H:%M:%S') if user.created_on else ''
        }

    unrecognized_user_data_keys = set()
    user_groups_length = 0
    max_location_length = 0
    user_dicts = []
    for n, user in enumerate(get_commcare_users_by_filters(domain, user_filters)):
        group_names = _get_group_names(user)
        user_dict = _make_user_dict(user, group_names, location_cache)
        user_dicts.append(user_dict)
        unrecognized_user_data_keys.update(user_dict['uncategorized_data'])
        user_groups_length = max(user_groups_length, len(group_names))
        max_location_length = max(max_location_length, len(user_dict["location_code"]))
        DownloadBase.set_progress(task, n, total_count)

    user_headers = [
        'username', 'password', 'name', 'phone-number', 'email',
        'language', 'role', 'user_id', 'is_active', 'User IMEIs (read only)',
        'registered_on (read only)']

    user_data_fields = [f.slug for f in user_data_model.get_fields(include_system=False)]
    user_headers.extend(build_data_headers(user_data_fields))
    user_headers.extend(build_data_headers(
        unrecognized_user_data_keys,
        header_prefix='uncategorized_data'
    ))
    user_headers.extend(json_to_headers(
        {'group': list(range(1, user_groups_length + 1))}
    ))
    if domain_has_privilege(domain, privileges.LOCATIONS):
        user_headers.extend(json_to_headers(
            {'location_code': list(range(1, max_location_length + 1))}
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
        group_data_keys.update(group.metadata if group.metadata else [])

    group_headers = ['id', 'name', 'case-sharing?', 'reporting?']
    group_headers.extend(build_data_headers(group_data_keys))

    def _get_group_rows():
        for group_dict in group_dicts:
            row = dict(flatten_json(group_dict))
            yield [row.get(header) or '' for header in group_headers]
    return group_headers, _get_group_rows()


def count_users_and_groups(domain, user_filters, group_memoizer):
    users_count = get_commcare_users_by_filters(domain, user_filters, count_only=True)
    groups_count = len(group_memoizer.groups)

    return users_count + groups_count


def dump_users_and_groups(domain, download_id, user_filters, task):
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

    writer = Excel2007ExportWriter(format_as_text=True)
    group_memoizer = _load_memoizer(domain)
    location_cache = LocationIdToSiteCodeCache(domain)

    users_groups_count = count_users_and_groups(domain, user_filters, group_memoizer)
    DownloadBase.set_progress(task, 0, users_groups_count)

    user_data_model = CustomDataFieldsDefinition.get_or_create(
        domain,
        UserFieldsView.field_type
    )

    user_headers, user_rows = parse_users(
        group_memoizer,
        domain,
        user_data_model,
        location_cache,
        user_filters,
        task,
        users_groups_count,
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

    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    filename = "{}_users_{}.xlsx".format(domain, uuid.uuid4().hex)
    file_path = get_download_file_path(use_transfer, filename)
    writer.open(
        header_table=headers,
        file=file_path,
    )
    writer.write(rows)
    writer.close()

    expose_download(use_transfer, file_path, filename, download_id, 'xlsx')
    DownloadBase.set_progress(task, users_groups_count, users_groups_count)


class GroupNameError(Exception):

    def __init__(self, blank_groups):
        self.blank_groups = blank_groups

    @property
    def message(self):
        return "The following group ids have a blank name: %s." % (
            ', '.join([group.get_id for group in self.blank_groups])
        )
