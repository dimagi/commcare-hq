from StringIO import StringIO
from couchdbkit.exceptions import MultipleResultsFound, ResourceNotFound
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from corehq.apps.groups.models import Group
from corehq.apps.users.util import normalize_username, raw_username
from corehq.apps.users.models import CommCareUser
from couchexport.writers import Excel2007ExportWriter
from dimagi.utils.excel import flatten_json, json_to_headers, \
    alphanumeric_sort_key


class UserUploadError(Exception):
    pass


required_headers = set(['username'])
allowed_headers = set(['password', 'phone-number', 'email', 'user_id', 'name', 'group', 'data', 'language']) | required_headers

    
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

def create_or_update_groups(domain, group_specs, log):
    group_memoizer = GroupMemoizer(domain)
    group_memoizer.load_all()
    group_names = set()
    for row in group_specs:
        group_id = row.get('id')
        group_name = row.get('name')
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


def create_or_update_users_and_groups(domain, user_specs, group_specs):
    ret = {"errors": [], "rows": []}
    group_memoizer = create_or_update_groups(domain, group_specs, log=ret)
    usernames = set()
    user_ids = set()

    allowed_groups = set(group_memoizer.groups)
    allowed_group_names = [group.name for group in allowed_groups]

    try:
        for row in user_specs:
            data, email, group_names, language, name, password, phone_number, user_id, username = (
                row.get(k) for k in sorted(allowed_headers)
            )
            if password:
                password = unicode(password)
            group_names = group_names or []
            try:
                username = normalize_username(username, domain)
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
                        for c in password:
                            if c != "*":
                                return True
                        return bool(password)

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
                        if not is_password(password):
                            raise UserUploadError(_("Cannot create a new user with a blank password"))
                        user = CommCareUser.create(domain, username, password, uuid=user_id or '')
                        status_row['flag'] = 'created'
                    if phone_number:
                        user.add_phone_number(_fmt_phone(phone_number), default=True)
                    if name:
                        user.set_full_name(name)
                    if data:
                        user.user_data.update(data)
                    if language:
                        user.language = language
                    if email:
                        user.email = email
                    user.save()
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

                except UserUploadError as e:
                    status_row['flag'] = '%s' % e
                    
            ret["rows"].append(status_row)
    finally:
        group_memoizer.save_all()
    
    return ret


class GroupNameError(Exception):
    def __init__(self, blank_groups):
        self.blank_groups = blank_groups

    @property
    def message(self):
        return "The following group ids have a blank name: %s." % (
            ', '.join([group.get_id for group in self.blank_groups])
        )


def dump_users_and_groups(response, domain):
    file = StringIO()
    writer = Excel2007ExportWriter()

    users = CommCareUser.by_domain(domain)
    user_data_keys = set()
    user_groups_length = 0
    user_dicts = []
    group_data_keys = set()
    group_dicts = []
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

    for user in users:
        data = user.user_data
        group_names = sorted(map(
            lambda id: group_memoizer.get(id).name,
            Group.by_user(user, wrap=False)
        ), key=alphanumeric_sort_key)
        # exclude password and user_id
        user_dicts.append({
            'data': data,
            'group': group_names,
            'name': user.full_name,
            # dummy display string for passwords
            'password': "********", 
            'phone-number': user.phone_number,
            'email': user.email,
            'username': user.raw_username,
            'language': user.language,
        })
        user_data_keys.update(user.user_data.keys() if user.user_data else {})
        user_groups_length = max(user_groups_length, len(group_names))

    sorted_groups = sorted(group_memoizer.groups, key=lambda group: alphanumeric_sort_key(group.name))
    for group in sorted_groups:
        group_dicts.append({
            'id': group.get_id,
            'name': group.name,
            'case-sharing': group.case_sharing,
            'reporting': group.reporting,
            'data': group.metadata,
        })
        group_data_keys.update(group.metadata.keys() if group.metadata else {})

    # include obscured password column for adding new users
    user_headers = ['username', 'password', 'name', 'phone-number', 'email', 'language']
    user_headers.extend(json_to_headers(
        {'data': dict([(key, None) for key in user_data_keys])}
    ))
    user_headers.extend(json_to_headers(
        {'group': range(1, user_groups_length + 1)}
    ))

    group_headers = ['id', 'name', 'case-sharing?', 'reporting?']
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
