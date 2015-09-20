from __future__ import absolute_import
from collections import namedtuple
import logging

from couchdbkit import BulkSaveError, ResourceNotFound, MultipleResultsFound
from dimagi.utils.decorators.memoized import memoized
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


class BadUsername(Exception):
    pass


class BadIsActive(Exception):
    pass

UserSpec = namedtuple('UserSpec', [
    'data',
    'email',
    'group_names',
    'language',
    'name',
    'password',
    'phone_number',
    'uncategorized_data',
    'user_id',
    'username',
    'location_code',
    'is_active',
])


def create_or_update_users_groups_and_locations(domain, user_specs, group_specs, location_specs, task=None):
    user_specs_input = user_specs
    user_specs = []
    for user_spec in user_specs_input:
        user_specs.append(UserSpec(
            data=user_spec.get('data'),
            email=user_spec.get('email'),
            group_names=map(unicode, user_spec.get('group') or []),
            language=user_spec.get('language'),
            name=user_spec.get('name'),
            password=user_spec.get('password'),
            phone_number=user_spec.get('phone-number'),
            uncategorized_data=user_spec.get('uncategorized_data'),
            user_id=user_spec.get('user_id'),
            username=user_spec.get('username'),
            location_code=user_spec.get('location-sms-code', ''),
            is_active=user_spec.get('is_active'),
        ))
    return _Creator(domain, user_specs, group_specs, location_specs, task=task).create_or_update_users_groups_and_locations()


def normalize_user_spec(user_spec, domain):

    def _normalize_username(username):
        try:
            return normalize_username(str(username), domain)
        except TypeError:
            return None
        except ValidationError:
            raise BadUsername()

    def _normalize_password(password):
        if password:
            password = unicode(password)
            if password[0] != '*':
                return password
        return None

    def _normalize_is_active(is_active):
        if isinstance(user_spec.is_active, basestring):
            try:
                return string_to_boolean(is_active)
            except ValueError:
                raise BadIsActive()

    return user_spec._replace(
        username=_normalize_username(user_spec.username),
        password=_normalize_password(user_spec.password),
        is_active=_normalize_is_active(user_spec.is_active))


class _Creator(object):
    def __init__(self, domain, user_specs, group_specs, location_specs, task=None):
        self.domain = domain
        self.user_specs = user_specs
        self.group_specs = group_specs
        self.location_specs = location_specs
        self.task = task
        self.total = len(self.user_specs) + len(self.group_specs) + len(self.location_specs)
        self.group_memoizer = GroupMemoizer(self.domain)
        self.errors_to_return = []
        self.user_statuses_to_return = []

    def create(self):
        self.group_memoizer.load_all()
        return self.create_or_update_users_groups_and_locations()

    def _set_progress(self, progress):
        if self.task is not None:
            DownloadBase.set_progress(self.task, progress, self.total)

    def record_error(self, error_string):
        self.errors_to_return.append(error_string)

    def record_user_update(self, user_spec, message):
        username = raw_username(user_spec.username) if user_spec.username else None,
        self.user_statuses_to_return.append({
            'username': username,
            'row': user_spec,
            'flag': message,
        })

    @property
    @memoized
    def can_access_locations(self):
        return domain_has_privilege(self.domain, privileges.LOCATIONS)

    @property
    @memoized
    def location_cache(self):
        return SiteCodeToLocationCache(self.domain)

    @property
    @memoized
    def supports_multiple_locations_per_user(self):
        return Domain.get_by_name(self.domain).supports_multiple_locations_per_user

    def create_or_update_users_groups_and_locations(self):

        self.create_or_update_groups()

        self.create_or_update_users()
        if self.supports_multiple_locations_per_user:
            self.create_or_update_locations()
        self._set_progress(self.total)
        return {'errors': self.errors_to_return,
                'rows': self.user_statuses_to_return}

    def create_or_update_users(self):
        try:
            self._do_most_of_create_users()
        finally:
            try:
                self.group_memoizer.save_all()
            except BulkSaveError as e:
                self._log_bulk_save_error(e)

    def _log_bulk_save_error(self, e):
        _error_message = _(
            "Oops! We were not able to save some of your group changes. "
            "Please make sure no one else is editing your groups "
            "and try again.")
        logging.exception((
            'BulkSaveError saving groups. '
            'User saw error message "%s". Errors: %s'
        ) % (_error_message, e.errors))
        self.record_error(_error_message)

    def create_or_update_groups(self):
        group_names = set()
        for group_spec in self.group_specs:
            self._create_or_update_single_group(group_spec, group_names)

    def _create_or_update_single_group(self, group_spec, group_names):
        group_id = group_spec.get('id')
        group_name = unicode(group_spec.get('name') or '')
        case_sharing = group_spec.get('case-sharing')
        reporting = group_spec.get('reporting')
        data = group_spec.get('data')

        # check that group_names are unique
        if group_name in group_names:
            self.record_error('Your spreadsheet has multiple groups called "%s" and only the first was processed' % group_name)
            return
        else:
            group_names.add(group_name)

        # check that there's a group_id or a group_name
        if not group_id and not group_name:
            self.record_error('Your spreadsheet has a group with no name or id and it has been ignored')
            return

        try:
            if group_id:
                group = self.group_memoizer.get(group_id)
            else:
                group = self.group_memoizer.by_name(group_name)
                if not group:
                    group = self.group_memoizer.create(domain=self.domain, name=group_name)
        except ResourceNotFound:
            self.record_error('There are no groups on CommCare HQ with id "%s"' % group_id)
        except MultipleResultsFound:
            self.record_error("There are multiple groups on CommCare HQ named: %s" % group_name)
        else:
            if group_name:
                self.group_memoizer.rename_group(group, group_name)
            group.case_sharing = case_sharing
            group.reporting = reporting
            group.metadata = data

    def create_or_update_locations(self):
        """
        This method should only be used when uploading multiple
        location per user situations. This is behind a feature
        flag and is not for normal use.

        It is special because it is creating delegate case
        submissions to give this location access.
        """
        sp_cache = SiteCodeToSupplyPointCache(self.domain)
        users = {}
        for row in self.location_specs:
            username = row.get('username')
            try:
                username = normalize_username(username, self.domain)
            except ValidationError:
                self.record_error(
                    _("Username must be a valid email address: %s") % username
                )
            else:
                location_code = unicode(row.get('location-sms-code'))
                if username in users:
                    user_mapping = users[username]
                else:
                    user_mapping = UserLocMapping(username, self.domain, sp_cache)
                    users[username] = user_mapping

                if row.get('remove') == 'y':
                    user_mapping.to_remove.add(location_code)
                else:
                    user_mapping.to_add.add(location_code)

        for username, mapping in users.iteritems():
            try:
                messages = mapping.save()
                for message in messages:
                    self.record_error(message)
            except UserUploadError as e:
                self.record_error(
                    _('Unable to update locations for {user} because {message}'.format(
                        user=username,
                        message=e
                    ))
                )

    @property
    @memoized
    def custom_data_validator(self):
        from corehq.apps.users.views.mobile import UserFieldsView
        return UserFieldsView.get_validator(self.domain)

    def _do_most_of_create_users(self):
        usernames = set()
        user_ids = set()
        allowed_group_names = [group.name for group in self.group_memoizer.groups]

        starting_progress = len(self.group_specs)
        for i, user_spec in enumerate(self.user_specs):
            self._set_progress(starting_progress + i)
            message = self._create_or_update_single_user(
                user_spec=user_spec,
                usernames=usernames,
                user_ids=user_ids,
                allowed_group_names=allowed_group_names,
            )
            self.record_user_update(user_spec, message)

    def _create_or_update_single_user(self, user_spec, usernames, user_ids,
                                      allowed_group_names):
        try:
            user_spec = normalize_user_spec(user_spec, self.domain)
        except BadUsername:
            return _('username cannot contain spaces or symbols')
        except BadIsActive:
            return _("'is_active' column can only contain 'true' or 'false'")

        if user_spec.username in usernames or user_spec.user_id in user_ids:
            status_message = 'repeat'
        elif not user_spec.username and not user_spec.user_id:
            status_message = 'missing-data'
        else:
            try:
                if user_spec.username:
                    usernames.add(user_spec.username)
                if user_spec.user_id:
                    user_ids.add(user_spec.user_id)
                    user = CommCareUser.get_by_user_id(user_spec.user_id, self.domain)
                else:
                    user = CommCareUser.get_by_username(user_spec.username)

                if user:
                    if user.domain != self.domain:
                        raise UserUploadError(_(
                            'User with username %(username)r is '
                            'somehow in domain %(domain)r'
                        ) % {'username': user.username, 'domain': user.domain})
                    if user_spec.username and user.username != user_spec.username:
                        user.change_username(user_spec.username)
                    if user_spec.password:
                        user.set_password(user_spec.password)
                    status_message = 'updated'
                else:
                    if is_username_too_long(user_spec.username):
                        return _("username cannot contain greater than %d characters") \
                               % CommCareAccountForm.max_len_username
                    if not user_spec.password:
                        raise UserUploadError(_("Cannot create a new user with a blank password"))
                    user = CommCareUser.create(self.domain, user_spec.username, user_spec.password, commit=False)
                    status_message = 'created'

                self._update_user_from_spec(user, user_spec)
                user.save()
                if self.can_access_locations and user_spec.location_code:
                    loc = self.location_cache.get(user_spec.location_code)
                    if user.location_id != loc._id:
                        # this triggers a second user save so
                        # we want to avoid doing it if it isn't
                        # needed
                        user.set_location(loc)
                if user_spec.password:
                    # Without this line, digest auth doesn't work.
                    # With this line, digest auth works.
                    # Other than that, I'm not sure what's going on
                    user.get_django_user().check_password(user_spec.password)

                for group_id in Group.by_user(user, wrap=False):
                    group = self.group_memoizer.get(group_id)
                    if group.name not in user_spec.group_names:
                        group.remove_user(user, save=False)

                for group_name in user_spec.group_names:
                    if group_name not in allowed_group_names:
                        raise UserUploadError(_(
                            "Can't add to group '%s' "
                            "(try adding it to your spreadsheet)"
                        ) % group_name)
                    self.group_memoizer.by_name(group_name).add_user(user, save=False)

            except (UserUploadError, CouchUser.Inconsistent) as e:
                status_message = unicode(e)

        return status_message

    def _update_user_from_spec(self, user, user_spec):
        if user_spec.phone_number:
            user.add_phone_number(_fmt_phone(user_spec.phone_number), default=True)
        if user_spec.name:
            user.set_full_name(user_spec.name)
        if user_spec.data:
            error = self.custom_data_validator(user_spec.data)
            if error:
                raise UserUploadError(error)
            user.user_data.update(user_spec.data)
        if user_spec.uncategorized_data:
            user.user_data.update(user_spec.uncategorized_data)
        if user_spec.language:
            user.language = user_spec.language
        if user_spec.email:
            user.email = user_spec.email
        if user_spec.is_active is not None:
            user.is_active = user_spec.is_active


def _fmt_phone(phone_number):
    if phone_number and not isinstance(phone_number, basestring):
        phone_number = str(int(phone_number))
    return phone_number.lstrip("+")


def is_username_too_long(username):
    return len(raw_username(username)) > CommCareAccountForm.max_len_username
