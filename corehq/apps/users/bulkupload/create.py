from __future__ import absolute_import
import logging

from couchdbkit import BulkSaveError, ResourceNotFound, MultipleResultsFound
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

from corehq import privileges
from corehq.apps.accounting.utils import domain_has_privilege
from corehq.apps.domain.models import Domain
from corehq.apps.groups.models import Group
from corehq.apps.users.bulkupload.bulk_cache import SiteCodeToLocationCache
from corehq.apps.users.exceptions import UserUploadError
from corehq.apps.users.forms import CommCareAccountForm
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import normalize_username, raw_username
from dimagi.utils.parsing import string_to_boolean
from soil import DownloadBase
from .group_memoizer import GroupMemoizer
from .bulk_cache import SiteCodeToSupplyPointCache
from .bulkupload import UserLocMapping


def create_or_update_users_and_groups(domain, user_specs, group_specs, location_specs, task=None):
    from corehq.apps.users.views.mobile import UserFieldsView
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


def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, basestring):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")


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
