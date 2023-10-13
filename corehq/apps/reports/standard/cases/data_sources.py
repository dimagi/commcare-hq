import json
from datetime import date

from django.template.defaultfilters import yesno
from django.urls import NoReverseMatch
from django.utils.html import format_html
from django.utils.translation import gettext as _

import pytz
from couchdbkit import ResourceNotFound

from corehq.apps.case_search.const import (
    CASE_COMPUTED_METADATA,
    SPECIAL_CASE_PROPERTIES,
)
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.util import get_user_id_from_form
from corehq.apps.reports.v2.utils import report_date_to_json
from corehq.apps.users.models import CouchUser
from corehq.const import USER_DATETIME_FORMAT_WITH_SEC
from corehq.util.quickcache import quickcache
from corehq.util.timezones.utils import parse_date
from corehq.util.view_utils import absolute_reverse
from corehq.apps.hqcase.case_helper import CaseCopier
from corehq.form_processor.models import CommCareCase

CASE_COPY_PROPERTY = CaseCopier.COMMCARE_CASE_COPY_PROPERTY_NAME


class CaseDisplayBase:
    """This class wraps a raw case from ES to provide simpler access
    to certain properties as well as formatting for properties for use in
    the UI"""

    date_format = USER_DATETIME_FORMAT_WITH_SEC
    aliases = {
        'status': 'closed_display',
        'opened_by_username': 'creating_user',
        'owner_name': 'owner_display',
        'name': 'case_name',
        'date_opened': 'opened_on',
        'last_modified': 'modified_on',
    }

    def __init__(self, case, timezone=pytz.UTC, override_user_id=None):
        """
        case is a dict object of the case doc
        """
        self.case = case
        self.timezone = timezone
        self.override_user_id = override_user_id

    @property
    def case_name_display(self):
        return self.case_name or _('[no name]')

    @property
    def case_detail_url(self):
        try:
            return absolute_reverse('case_data', args=[self.domain, self.case_id])
        except NoReverseMatch:
            return None

    def _user_meta(self, user_id):
        return {'id': user_id, 'name': self._get_username(user_id)}

    @property
    @quickcache(['self.owner_id'])
    def location(self):
        return SQLLocation.objects.get_or_None(location_id=self.owner_id)

    @property
    @quickcache(['self.owner_id', 'self.user_id'])
    def owner(self):
        if not self.owner_id:
            return 'user', {'id': self.owner_id, 'name': self.owner_id}
        if self.owning_group and self.owning_group.name:
            return 'group', {'id': self.owning_group._id, 'name': self.owning_group.name}
        elif self.location:
            return ('location', {'id': self.location.location_id,
                                 'name': self.location.display_name})
        else:
            return 'user', self._user_meta(self.user_id)

    @property
    def owner_type(self):
        return self.owner[0]

    @property
    def user_id(self):
        return self.override_user_id or self.owner_id

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

    @property
    def closed_display(self):
        return yesno(self.is_closed, "closed,open")

    @property
    def case_link(self):
        url = self.case_detail_url
        if url:
            return format_html(
                "<a class='ajax_dialog' href='{}' target='_blank'>{}</a>{}",
                self.case_detail_url,
                self.case_name_display,
                additional_case_label(self.case),
            )
        else:
            return "%s (bad ID format)" % self.case_name

    def _fmt_date(self, value, is_phonetime=True):
        if not isinstance(value, date):
            return ''
        return report_date_to_json(
            value,
            self.timezone,
            self.date_format,
            is_phonetime=is_phonetime
        )

    @property
    def owner_display(self):
        owner_type, owner = self.owner
        if owner_type == 'group':
            return format_html('<span class="label label-default">{}</span>', owner['name'])
        else:
            return owner['name']

    def user_not_found_display(self, user_id):
        return _("Unknown [%s]") % user_id

    @property
    def creating_user(self):
        user = self._creating_user
        if user is None:
            return _("No data")
        else:
            return user['name'] or self.user_not_found_display(user['id'])

    @property
    def opened_by_user_id(self):
        user = self._creating_user
        if user is None:
            return _("No data")
        else:
            return user['id']

    def __getattr__(self, item):
        if item in self.aliases:
            return getattr(self, self.aliases[item])
        raise AttributeError(item)

    @property
    def last_modified_by_user_username(self):
        return self._get_username(self.last_modified_user_id)

    @property
    def closed_by_username(self):
        return self._get_username(self.closed_by_user_id)

    @property
    def domain(self):
        raise NotImplementedError

    @property
    def case_type(self):
        raise NotImplementedError

    @property
    def case_name(self):
        raise NotImplementedError

    @property
    def case_id(self):
        raise NotImplementedError

    @property
    def external_id(self):
        raise NotImplementedError

    @property
    def is_closed(self):
        raise NotImplementedError

    @property
    def _creating_user(self):
        raise NotImplementedError

    @property
    def owner_id(self):
        raise NotImplementedError

    @property
    def opened_on(self):
        raise NotImplementedError

    @property
    def modified_on(self):
        raise NotImplementedError

    @property
    def closed_on(self):
        raise NotImplementedError

    @property
    def server_last_modified_date(self):
        raise NotImplementedError

    @property
    def closed_by_user_id(self):
        raise NotImplementedError

    @property
    def last_modified_user_id(self):
        raise NotImplementedError


class CaseDisplayES(CaseDisplayBase):
    """This class wraps a raw case from ES to provide simpler access
    to certain properties as well as formatting for properties for use in
    the UI"""

    @property
    def domain(self):
        return self.case['domain']

    @property
    def case_type(self):
        return self.case['type']

    @property
    def case_name(self):
        return self.case['name']

    @property
    def case_id(self):
        return self.case['_id']

    @property
    def external_id(self):
        return self.case['external_id']

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
                        creator_id = get_user_id_from_form(action["xform_id"])
                        break

        if not creator_id:
            return None
        return self._user_meta(creator_id)

    @property
    def owner_id(self):
        if 'owner_id' in self.case:
            return self.case['owner_id']
        elif 'user_id' in self.case:
            return self.case['user_id']
        else:
            return ''

    @property
    def opened_on(self):
        return self._fmt_date(parse_date(self.case['opened_on']))

    @property
    def modified_on(self):
        return self._fmt_date(parse_date(self.case['modified_on']))

    @property
    def closed_on(self):
        return self._fmt_date(parse_date(self.case['closed_on']))

    @property
    def server_last_modified_date(self):
        return self._fmt_date(parse_date(self.case['server_modified_on']), False)

    @property
    def closed_by_user_id(self):
        return self.case.get('closed_by')

    @property
    def last_modified_user_id(self):
        return self.case['user_id']


class CaseDisplaySQL(CaseDisplayBase):
    @property
    def domain(self):
        return self.case.domain

    @property
    def case_type(self):
        return self.case.type

    @property
    def case_name(self):
        return self.case.name

    @property
    def case_id(self):
        return self.case.case_id

    @property
    def external_id(self):
        return self.case.external_id

    @property
    def is_closed(self):
        return self.case.closed

    @property
    def _creating_user(self):
        try:
            creator_id = self.case.opened_by
        except KeyError:
            return None

        return self._user_meta(creator_id)

    @property
    def owner_id(self):
        return self.case.owner_id or self.case.user_id or ''

    @property
    def opened_on(self):
        return self._fmt_date(self.case.opened_on)

    @property
    def modified_on(self):
        return self._fmt_date(self.case.modified_on)

    @property
    def closed_on(self):
        return self._fmt_date(self.case.closed_on)

    @property
    def server_last_modified_date(self):
        return self._fmt_date(self.case.server_modified_on, False)

    @property
    def closed_by_user_id(self):
        return self.case.closed_by

    @property
    def last_modified_user_id(self):
        return self.case.user_id


class SafeCaseDisplay(object):
    """Show formatted properties if they are used in XML, otherwise show the property directly from the case
    """
    def __init__(self, case, timezone=None, override_user_id=None):
        self.case = case
        if timezone is None:
            timezone = pytz.UTC
        self.display = CaseDisplaySQL(self.case, timezone, override_user_id)

    def get(self, name):
        if name == '_link':
            return self._link

        if name == 'indices':
            return json.dumps([index.to_json() for index in self.case.indices])

        if name in (SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA):
            return getattr(self.display, name.replace('@', ''))

        return self.case.get_case_property(name)

    @property
    def _link(self):
        try:
            link = absolute_reverse('case_data', args=[self.case.domain, self.case.case_id])
        except NoReverseMatch:
            return _("No link found")

        return format_html(
            "<a class='ajax_dialog' href='{}' target='_blank'>{}</a>{}",
            link,
            _("View Case"),
            additional_case_label(self.case),
        )


def additional_case_label(case):
    copy_label = format_html(
        '&nbsp;<span class="label label-info" title="0">{}</span>',
        _("Copied case"),
    )
    if isinstance(case, CommCareCase) and case.get_case_property(CASE_COPY_PROPERTY):
        return copy_label
    if not isinstance(case, CommCareCase) and case.get(CASE_COPY_PROPERTY):
        return copy_label
    return ''
