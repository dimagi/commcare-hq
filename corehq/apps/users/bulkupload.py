from StringIO import StringIO
from couchdbkit.exceptions import MultipleResultsFound
from django.contrib import messages
from corehq.apps.groups.models import Group
from corehq.apps.users.util import normalize_username, raw_username
from corehq.apps.users.models import CommCareUser
from django.db.utils import DatabaseError
from django.db import transaction
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.decorators.profile import profile
from dimagi.utils.excel import flatten_json, json_to_headers, alphanumeric_sort_key

required_headers = set(['username'])
allowed_headers = set(['password', 'phone-number', 'user_id', 'name', 'group', 'data']) | required_headers

    
def check_headers(user_specs):
    headers = set(user_specs.fieldnames)

    illegal_headers = headers - allowed_headers
    missing_headers = required_headers - headers

    messages = []
    for header_set, label in (missing_headers, 'required'), (illegal_headers, 'illegal'):
        if header_set:
            messages.append('The following are %s column headers: %s.' % (label, ', '.join(header_set)))
    if messages:
        raise Exception('\n'.join(messages))

class GroupMemoizer(object):
    def __init__(self, domain):
        self.groups = {}
        self.domain = domain

    def get_or_create_group(self, group_name):
        return self.get_group(group_name, load_if_not_loaded=True)

    def get_group(self, group_name, load_if_not_loaded=False):
        if load_if_not_loaded and not self.groups.has_key(group_name):
            group = Group.by_name(self.domain, group_name)
            if group:
                self.groups[group_name] = group
            else:
                self.groups[group_name] = Group(domain=self.domain, name=group_name)
        return self.groups[group_name]

    def delete_other(self):
        all_groups = Group.by_domain(self.domain)
        records = []
        for group in all_groups:
            if not self.groups.has_key(group.name):
                record = group.soft_delete()
                records.append(record)
        return records

    def save_all(self):
        for group in self.groups.values():
            group.save()

def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, basestring):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")

def create_or_update_users_and_groups(domain, user_specs, group_specs):
    group_memoizer = GroupMemoizer(domain)
    ret = {"errors": [], "rows": []}
    for row in group_specs:
        group_name, case_sharing, reporting, data = row['name'], row.get('case-sharing'), row.get('reporting'), row.get('data')
        try:
            group = group_memoizer.get_or_create_group(group_name)
        except MultipleResultsFound:
            ret["errors"].append("Multiple groups named: %s" % group_name)
        else:
            group.case_sharing = case_sharing
            group.reporting = reporting
            group.metadata = data
    usernames = set()
    user_ids = set()

    try:
        for row in user_specs:
            data, group_names, name, password, phone_number, user_id, username = (
                row.get(k) for k in sorted(allowed_headers)
            )
            if isinstance(password, float):
                # almost certainly what was intended
                password = unicode(int(password))
            group_names = group_names or []
            try:
                username = normalize_username(username, domain)
            except TypeError:
                username = None
            status_row = {
                'username': raw_username(username) if username else None,
                'row': row,
            }
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
                    if user:
                        if user.domain != domain:
                            raise Exception('User with username %r is somehow in domain %r' % (user.username, user.domain))
                        if username and user.username != username:
                            user.change_username(username)
                        if password:
                            user.set_password(password)
                        status_row['flag'] = 'updated'
                    else:
                        if not password:
                            raise Exception("Cannot create a new user with a blank password")
                        user = CommCareUser.create(domain, username, password, uuid=user_id or '')
                        status_row['flag'] = 'created'
                    if phone_number:
                        user.add_phone_number(_fmt_phone(phone_number), default=True)
                    if name:
                        user.set_full_name(name)
                    if data:
                        user.user_data.update(data)
                    user.save()
                    if password:
                        # Without this line, digest auth doesn't work.
                        # With this line, digest auth works.
                        # Other than that, I'm not sure what's going on
                        user.get_django_user().check_password(password)
                    for group in Group.by_user(user):
                        if group.name not in group_names:
                            group = group_memoizer.get_or_create_group(group.name)
                            group.remove_user(user)

                    for group_name in group_names:
                        try:
                            group_memoizer.get_group(group_name).add_user(user)
                        except Exception:
                            raise Exception("Can't add to group '%s' (try adding it to your spreadsheet)" % group_name)
                except Exception, e:
                    if isinstance(e, DatabaseError):
                        transaction.rollback()
                    status_row['flag'] = 'error: %s' % e
                    
            ret["rows"].append(status_row)
    finally:
        group_memoizer.save_all()
    
    return ret

class UsersDumpHelper(object):

    def __init__(self):
        self.groups = {}

    def get_group(self, id):
        if not self.groups.has_key(id):
            self.groups[id] = Group.get(id)
        return self.groups[id]

    def get_group_name(self, id):
        return self.get_group(id).name

    def get_all_groups(self):
        # sort in memory
        return sorted(self.groups.values(), key=lambda group: group.name)

def dump_users_and_groups(response, domain):

    file = StringIO()
    writer = Excel2007ExportWriter()

    users = CommCareUser.by_domain(domain)
    user_data_keys = set()
    user_groups_length = 0
    user_dicts = []
    group_data_keys = set()
    group_dicts = []
    helper = UsersDumpHelper()

    for user in users:
        data = user.user_data
        group_names = sorted(map(
            helper.get_group_name,
            Group.by_user(user, wrap=False)
        ), key=alphanumeric_sort_key)
        # exclude password and user_id
        user_dicts.append({
            'data': data,
            'group': group_names,
            'name': user.full_name,
            'phone-number': user.phone_number,
            'username': user.raw_username,
        })
        user_data_keys.update(user.user_data.keys())
        user_groups_length = max(user_groups_length, len(group_names))

    for group in helper.get_all_groups():
        group_dicts.append({
            'name': group.name,
            'case-sharing': group.case_sharing,
            'reporting': group.reporting,
            'data': group.metadata,
        })
        group_data_keys.update(group.metadata.keys())


    user_headers = ['username', 'name', 'phone-number']
    user_headers.extend(json_to_headers(
        {'data': dict([(key, None) for key in user_data_keys])}
    ))
    user_headers.extend(json_to_headers(
        {'group': range(1, user_groups_length + 1)}
    ))

    group_headers = ['name', 'case-sharing?', 'reporting?']
    group_headers.extend(json_to_headers(
        {'data': dict([(key, None) for key in group_data_keys])}
    ))

    writer.open(
        header_table=[
            ('users', [user_headers]),
            ('groups', [group_headers]),
        ],
        file=file,
    )

    def get_user_rows():
        for user_dict in user_dicts:
            row = dict(flatten_json(user_dict))
            yield [row.get(header) or '' for header in user_headers]

    def get_group_rows():
        for group_dict in group_dicts:
            row = dict(flatten_json(group_dict))
            yield [row.get(header) or '' for header in group_headers]

    writer.write([
        ('users', get_user_rows()),
        ('groups', get_group_rows()),
    ])

    writer.close()
    response.write(file.getvalue())