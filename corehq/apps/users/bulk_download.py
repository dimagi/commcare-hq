import uuid

from django.conf import settings
from django.utils.translation import ugettext

from couchexport.writers import Excel2007ExportWriter
from soil import DownloadBase
from soil.util import expose_download, get_download_file_path

from corehq import privileges
from corehq import toggles
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.custom_data_fields.models import (
    PROFILE_SLUG,
    CustomDataFieldsDefinition,
    CustomDataFieldsProfile,
)
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.user_importer.importer import BulkCacheBase, GroupMemoizer
from corehq.apps.users.dbaccessors.all_commcare_users import (
    get_commcare_users_by_filters,
    get_mobile_usernames_by_filters,
    get_all_user_rows,
    get_web_user_count,
)
from corehq.apps.users.models import CouchUser, UserRole, Invitation
from corehq.util.workbook_json.excel import (
    alphanumeric_sort_key,
    flatten_json,
    json_to_headers,
)
from couchdbkit import ResourceNotFound


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

def get_devices(user):
    """
    Returns a comma-separated list of IMEI numbers of the user's devices, sorted with most-recently-used first
    """
    return ', '.join([device.device_id for device in sorted(
        user.devices, key=lambda d: d.last_used, reverse=True
    )])


def make_mobile_user_dict(user, group_names, location_cache, domain, fields_definition):
    model_data = {}
    uncategorized_data = {}
    model_data, uncategorized_data = (
        fields_definition.get_model_and_uncategorized(user.metadata)
    )
    role = user.get_role(domain)
    profile = None
    if PROFILE_SLUG in user.metadata and domain_has_privilege(domain, privileges.APP_USER_PROFILES):
        try:
            profile = CustomDataFieldsProfile.objects.get(id=user.metadata[PROFILE_SLUG])
        except CustomDataFieldsProfile.DoesNotExist:
            profile = None
    activity = user.reporting_metadata

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

    def _format_date(date):
        return date.strftime('%Y-%m-%d %H:%M:%S') if date else ''

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
        'User IMEIs (read only)': get_devices(user),
        'location_code': location_codes,
        'role': role.name if role else '',
        'domain': domain,
        'user_profile': profile.name if profile else '',
        'registered_on (read only)': _format_date(user.created_on),
        'last_submission (read only)': _format_date(activity.last_submission_for_user.submission_date),
        'last_sync (read only)': activity.last_sync_for_user.sync_date,
    }


def get_user_role_name(domain_membership):
    if domain_membership.is_admin:
        return ugettext('Admin')
    else:
        role_name = ''
        if domain_membership.role_id:
            try:
                role_name = UserRole.get(domain_membership.role_id).name
            except ResourceNotFound:
                role_name = ugettext('Unknown Role')
    return role_name


def make_web_user_dict(user, domain):
    user = CouchUser.wrap_correctly(user['doc'])
    domain_membership = user.get_domain_membership(domain)
    role_name = get_user_role_name(domain_membership)
    return {
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'role': role_name,
        'status': ugettext('Active User'),
        'last_access_date (read only)': domain_membership.last_accessed,
        'last_login (read only)': user.last_login,
        'remove': '',
    }


def make_invited_web_user_dict(invite):
    return {
        'username': invite.email,
        'first_name': 'N/A',
        'last_name': 'N/A',
        'email': invite.email,
        'role': invite.get_role_name(),
        'status': ugettext('Invited'),
        'last_access_date (read only)': 'N/A',
        'last_login (read only)': 'N/A',
        'remove': '',
    }


def get_user_rows(user_dicts, user_headers):
    for user_dict in user_dicts:
        row = dict(flatten_json(user_dict))
        yield [row.get(header, '') for header in user_headers]


def parse_mobile_users(domain, user_filters, task=None, total_count=None):
    from corehq.apps.users.views.mobile.custom_data_fields import UserFieldsView
    fields_definition = CustomDataFieldsDefinition.get_or_create(
        domain,
        UserFieldsView.field_type
    )
    location_cache = LocationIdToSiteCodeCache(domain)

    unrecognized_user_data_keys = set()
    user_groups_length = 0
    max_location_length = 0
    user_dicts = []
    domains_list = [domain]
    is_multi_domain_download = False
    if 'domains' in user_filters:
        domains_list = user_filters['domains']
    if domains_list != [domain]:
        is_multi_domain_download = True

    for current_domain in domains_list:
        for n, user in enumerate(get_commcare_users_by_filters(current_domain, user_filters)):
            group_memoizer = load_memoizer(current_domain)
            group_names = sorted([
                group_memoizer.get(id).name for id in Group.by_user_id(user.user_id, wrap=False)
            ], key=alphanumeric_sort_key)
            user_dict = make_mobile_user_dict(user, group_names, location_cache, current_domain, fields_definition)
            user_dicts.append(user_dict)
            unrecognized_user_data_keys.update(user_dict['uncategorized_data'])
            user_groups_length = max(user_groups_length, len(group_names))
            max_location_length = max(max_location_length, len(user_dict["location_code"]))
            if task:
                DownloadBase.set_progress(task, n, total_count)

    user_headers = [
        'username', 'password', 'name', 'phone-number', 'email',
        'language', 'role', 'user_id', 'is_active', 'User IMEIs (read only)',
        'registered_on (read only)', 'last_submission (read only)', 'last_sync (read only)'
    ]

    if domain_has_privilege(domain, privileges.APP_USER_PROFILES):
        user_headers += ['user_profile']
    user_data_fields = [f.slug for f in fields_definition.get_fields(include_system=False)]
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
    if is_multi_domain_download:
        user_headers += ['domain']
    return user_headers, get_user_rows(user_dicts, user_headers)


def parse_web_users(domain, task=None, total_count=None):
    user_dicts = []
    for n, user in enumerate(get_all_user_rows(domain, include_web_users=True, include_mobile_users=False,
                                               include_inactive=False, include_docs=True)):
        user_dict = make_web_user_dict(user, domain)
        user_dicts.append(user_dict)
        if task:
            DownloadBase.set_progress(task, n, total_count)
    for m, invite in enumerate(Invitation.by_domain(domain)):
        user_dict = make_invited_web_user_dict(invite)
        user_dicts.append(user_dict)
        if task:
            DownloadBase.set_progress(task, n + m, total_count)

    user_headers = [
        'username', 'first_name', 'last_name', 'email', 'role', 'last_access_date (read only)',
        'last_login (read only)', 'status', 'remove'
    ]
    return user_headers, get_user_rows(user_dicts, user_headers)


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
            yield [row.get(header, '') for header in group_headers]
    return group_headers, _get_group_rows()


def count_users_and_groups(domain, user_filters, group_memoizer):
    users_count = get_commcare_users_by_filters(domain, user_filters, count_only=True)
    groups_count = len(group_memoizer.groups)

    return users_count + groups_count


def dump_usernames(domain, download_id, user_filters, task, owner_id):
    domains_list = [domain]
    if 'domains' in user_filters:
        domains_list = user_filters['domains']  # for instances of multi-domain download
    users_count = 0
    for download_domain in domains_list:
        users_count += get_commcare_users_by_filters(download_domain, user_filters, count_only=True)
    DownloadBase.set_progress(task, 0, users_count)

    usernames = []
    for download_domain in domains_list:
        usernames += get_mobile_usernames_by_filters(download_domain, user_filters)

    headers = [('users', [['username']])]
    rows = [('users', [[username] for username in usernames])]
    location_id = user_filters.get('location_id')
    location_name = ""
    if location_id:
        location = SQLLocation.active_objects.get_or_None(location_id=location_id)
        location_name = location.name if location else ""
    filename_prefix = "_".join([a for a in [domain, location_name] if bool(a)])
    filename = "{}_users.xlsx".format(filename_prefix)
    _dump_xlsx_and_expose_download(filename, headers, rows, download_id, task, users_count, owner_id)


def _dump_xlsx_and_expose_download(filename, headers, rows, download_id, task, total_count, owner_id):
    writer = Excel2007ExportWriter(format_as_text=True)
    use_transfer = settings.SHARED_DRIVE_CONF.transfer_enabled
    file_path = get_download_file_path(use_transfer, filename)
    writer.open(
        header_table=headers,
        file=file_path,
    )
    writer.write(rows)
    writer.close()

    expose_download(use_transfer, file_path, filename, download_id, 'xlsx', owner_ids=[owner_id])
    DownloadBase.set_progress(task, total_count, total_count)


def load_memoizer(domain):
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


def dump_users_and_groups(domain, download_id, user_filters, task, owner_id):

    domains_list = user_filters['domains']

    users_groups_count = 0
    groups = set()
    for current_domain in domains_list:
        group_memoizer = load_memoizer(current_domain)
        users_groups_count += count_users_and_groups(current_domain, user_filters, group_memoizer)
        groups.update(group_memoizer.groups)

    DownloadBase.set_progress(task, 0, users_groups_count)

    user_headers, user_rows = parse_mobile_users(
        domain,
        user_filters,
        task,
        users_groups_count,
    )

    group_headers, group_rows = parse_groups(groups)
    headers = [
        ('users', [user_headers]),
        ('groups', [group_headers]),
    ]
    rows = [
        ('users', user_rows),
        ('groups', group_rows),
    ]

    filename = "{}_users_{}.xlsx".format(domain, uuid.uuid4().hex)
    _dump_xlsx_and_expose_download(filename, headers, rows, download_id, task, users_groups_count, owner_id)


def dump_web_users(domain, download_id, task, owner_id):
    users_count = get_web_user_count(domain, include_inactive=False)
    DownloadBase.set_progress(task, 0, users_count)

    user_headers, user_rows = parse_web_users(domain, task, users_count)

    headers = [('users', [user_headers])]
    rows = [('users', user_rows)]

    filename = "{}_users_{}.xlsx".format(domain, uuid.uuid4().hex)
    _dump_xlsx_and_expose_download(filename, headers, rows, download_id, task, users_count, owner_id)


class GroupNameError(Exception):

    def __init__(self, blank_groups):
        self.blank_groups = blank_groups

    @property
    def message(self):
        return "The following group ids have a blank name: %s." % (
            ', '.join([group.get_id for group in self.blank_groups])
        )
