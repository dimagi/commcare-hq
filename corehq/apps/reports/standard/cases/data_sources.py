import datetime
import json

import pytz
from django.template.defaultfilters import yesno
from django.urls import NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import ugettext as _

import dateutil
from couchdbkit import ResourceNotFound
from memoized import memoized

from casexml.apps.case.models import CommCareCaseAction

from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES,
)
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.util.dates import iso_string_to_datetime
from corehq.util.quickcache import quickcache
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.view_utils import absolute_reverse


class CaseDisplay:
    """This class wraps a raw case from ES to provide simpler access
    to certain properties as well as formatting for properties for use in
    the UI"""

    date_format = USER_DATETIME_FORMAT_WITH_SEC

    def __init__(self, case, timezone=pytz.UTC, override_user_id=None):
        """
        case is a dict object of the case doc
        """
        self.case = case
        self.timezone = timezone
        self.override_user_id = override_user_id

    @property
    def case_type(self):
        return self.case['type']

    @property
    def case_name(self):
        return self.case['name']
    name = case_name

    @property
    def case_name_display(self):
        return self.case_name or _('[no name]')

    @property
    def case_id(self):
        return self.case['_id']

    @property
    def external_id(self):
        return self.case['external_id']

    @property
    def case_detail_url(self):
        try:
            return absolute_reverse('case_data', args=[self.case['domain'], self.case_id])
        except NoReverseMatch:
            return None

    @property
    def is_closed(self):
        return self.case['closed']

    @property
    def _creating_user(self):
        try:
            creator_id = self.case['opened_by']
        except KeyError:
            creator_id = None
            if 'actions' in self.case:
                for action in self.case['actions']:
                    if action['action_type'] == 'create':
                        action_doc = CommCareCaseAction.wrap(action)
                        creator_id = action_doc.get_user_id()
                        break

        if not creator_id:
            return None
        return self._user_meta(creator_id)

    def _user_meta(self, user_id):
        return {'id': user_id, 'name': self._get_username(user_id)}

    @property
    @quickcache(['self.owner_id'])
    def location(self):
        return SQLLocation.objects.get_or_None(location_id=self.owner_id)

    @property
    @quickcache(['self.owner_id', 'self.user_id'])
    def owner(self):
        if self.owning_group and self.owning_group.name:
            return ('group', {'id': self.owning_group._id, 'name': self.owning_group.name})
        elif self.location:
            return ('location', {'id': self.location.location_id,
                                 'name': self.location.display_name})
        else:
            return ('user', self._user_meta(self.user_id))

    @property
    def owner_type(self):
        return self.owner[0]

    @property
    def user_id(self):
        return self.override_user_id or self.owner_id

    @property
    def owner_id(self):
        if 'owner_id' in self.case:
            return self.case['owner_id']
        elif 'user_id' in self.case:
            return self.case['user_id']
        else:
            return ''

    @property
    @quickcache(['self.owner_id'])
    def owning_group(self):
        try:
            return Group.get(self.owner_id)
        except ResourceNotFound:
            return None

    @quickcache(['user_id'])
    def _get_username(self, user_id):
        if not user_id:
            return None

        try:
            user = CouchUser.get_by_user_id(user_id)
            if user:
                return user.username
        except CouchUser.AccountTypeError:
            return None

    def parse_date(self, date_string):
        try:
            return iso_string_to_datetime(date_string)
        except Exception:
            try:
                date_obj = dateutil.parser.parse(date_string)
                if isinstance(date_obj, datetime.datetime):
                    return date_obj.replace(tzinfo=None)
                else:
                    return date_obj
            except Exception:
                return date_string

    @property
    def closed_display(self):
        return yesno(self.is_closed, "closed,open")
    status = closed_display

    @property
    def case_link(self):
        url = self.case_detail_url
        if url:
            return format_html(
                "<a class='ajax_dialog' href='{}' target='_blank'>{}</a>",
                self.case_detail_url,
                self.case_name_display)
        else:
            return "%s (bad ID format)" % self.case_name

    def _dateprop(self, prop):
        date = self.parse_date(self.case[prop])
        if date:
            user_time = PhoneTime(date, self.timezone).user_time(self.timezone)
            return user_time.ui_string(self.date_format)
        else:
            return ''

    @property
    def opened_on(self):
        return self._dateprop('opened_on')
    date_opened = opened_on

    @property
    def modified_on(self):
        return self._dateprop('modified_on')
    last_modified = modified_on

    @property
    def closed_on(self):
        return self._dateprop('closed_on')

    @property
    def server_last_modified_date(self):
        return self._dateprop('server_modified_on')

    @property
    def owner_display(self):
        owner_type, owner = self.owner
        if owner_type == 'group':
            return format_html('<span class="label label-default">{}</span>', owner['name'])
        else:
            return owner['name']
    owner_name = owner_display

    def user_not_found_display(self, user_id):
        return _("Unknown [%s]") % user_id

    @property
    def creating_user(self):
        user = self._creating_user
        if user is None:
            return _("No data")
        else:
            return user['name'] or self.user_not_found_display(user['id'])
    opened_by_username = creating_user

    @property
    def opened_by_user_id(self):
        user = self._creating_user
        if user is None:
            return _("No data")
        else:
            return user['id']

    @property
    def last_modified_by_user_username(self):
        return self._get_username(self.case['user_id'])

    @property
    def closed_by_user_id(self):
        return self.case.get('closed_by')

    @property
    def closed_by_username(self):
        return self._get_username(self.closed_by_user_id)


class SafeCaseDisplay(object):
    """Show formatted properties if they are used in XML, otherwise show the property directly from the case
    """
    def __init__(self, case, timezone, override_user_id=None):
        self.case = case
        self.timezone = timezone
        self.override_user_id = override_user_id

    def get(self, name):
        if name == '_link':
            return self._link

        if name == 'indices':
            return json.dumps(self.case.get('indices', []))

        if name in (SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA):
            return getattr(CaseDisplay(self.case, self.timezone, self.override_user_id), name.replace('@', ''))

        return self.case.get(name)

    @property
    def _link(self):
        try:
            link = absolute_reverse('case_data', args=[self.case.get("domain"), self.case.get('_id')])
        except NoReverseMatch:
            return _("No link found")
        return format_html(
            "<a class='ajax_dialog' href='{}' target='_blank'>{}</a>",
            link,
            _("View Case"))
