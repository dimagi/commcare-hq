from __future__ import absolute_import
from __future__ import unicode_literals

from couchdbkit import ResourceNotFound

from django.urls import NoReverseMatch
from django.utils import html
from django.utils.translation import ugettext as _

from casexml.apps.case.models import CommCareCaseAction
from corehq.apps.case_search.const import (
    SPECIAL_CASE_PROPERTIES_MAP,
    SPECIAL_CASE_PROPERTIES,
    CASE_COMPUTED_METADATA,
)
from corehq.apps.es.case_search import flatten_result
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.v2.models import BaseDataFormatter
from corehq.apps.reports.v2.utils import report_date_to_json
from corehq.apps.users.models import CouchUser
from corehq.util.quickcache import quickcache
from corehq.util.timezones.utils import parse_date
from corehq.util.view_utils import absolute_reverse


class CaseDataFormatter(BaseDataFormatter):

    def __init__(self, request, domain, raw_data):
        super(CaseDataFormatter, self).__init__(request, domain, raw_data)
        self.raw_data = flatten_result(raw_data)

    @property
    def owner_id(self):
        """Special Case Property @owner_id"""
        if 'owner_id' in self.raw_data:
            return self.raw_data.get('owner_id')
        elif 'user_id' in self.raw_data:
            return self.raw_data.gert('user_id')
        else:
            return ''

    @property
    def date_opened(self):
        """Special Case Property date_opened"""
        return self._fmt_dateprop('opened_on', False)

    @property
    def last_modified(self):
        """Special Case Property last_modified"""
        return self._fmt_dateprop('modified_on', False)

    @property
    def closed_by_username(self):
        """Computed metadata"""
        return self._get_username(self.closed_by_user_id)

    @property
    def last_modified_by_user_username(self):
        """Computed metadata"""
        return self._get_username(self.raw_data.get('user_id'))

    @property
    def opened_by_username(self):
        """Computed metadata"""
        user = self._creating_user
        if user is None:
            return _("No Data")
        return user['name'] or self._user_not_found_display(user['id'])

    @property
    def owner_name(self):
        """Computed metadata"""
        owner_type, owner = self._owner
        if owner_type == 'group':
            return '<span class="label label-default">%s</span>' % owner['name']
        return owner['name']

    @property
    def closed_by_user_id(self):
        """Computed metadata"""
        return self.raw_data.get('closed_by')

    @property
    def opened_by_user_id(self):
        """Computed metadata"""
        user = self._creating_user
        if user is None:
            return _("No data")
        return user['id']

    @property
    def server_last_modified_date(self):
        """Computed metadata"""
        return self._fmt_dateprop('server_modified_on', False)

    def get_context(self):
        context = {}
        context.update(self.raw_data)
        context.update(self._case_info_context)
        context['_link'] = self._link
        return context

    @property
    def _link(self):
        try:
            return absolute_reverse(
                'case_data', args=[self.domain, self.raw_data.get('_id')]
            )
        except NoReverseMatch:
            return None

    @property
    def _case_info_context(self):
        context = {}
        for prop in SPECIAL_CASE_PROPERTIES + CASE_COMPUTED_METADATA:
            context[prop] = self._get_case_info_prop(prop)
        return context

    def _get_case_info_prop(self, prop):
        fmt_prop = prop.replace('@', '')
        if hasattr(self, fmt_prop):
            return getattr(self, fmt_prop)
        elif prop in SPECIAL_CASE_PROPERTIES:
            return self._get_special_property(prop)
        raise NotImplementedError(
            "CaseDataFormatter.{} not found".format(prop))

    def _get_special_property(self, prop):
        return (SPECIAL_CASE_PROPERTIES_MAP[prop]
            .value_getter(self.raw_data))

    def _fmt_dateprop(self, prop, iso=True):
        val = report_date_to_json(
            self.request,
            self.domain,
            parse_date(self.raw_data[prop])
        )
        if iso:
            val = 'T'.join(val.split(' ')) if val else None
        return val

    @property
    @quickcache(['self.owner_id'])
    def _owning_group(self):
        try:
            return Group.get(self.owner_id)
        except ResourceNotFound:
            return None

    @property
    @quickcache(['self.owner_id'])
    def _location(self):
        return SQLLocation.objects.get_or_None(location_id=self.owner_id)

    @property
    @quickcache(['self.owner_id'])
    def _owner(self):
        if self._owning_group and self._owning_group.name:
            return ('group', {'id': self._owning_group._id,
                              'name': self._owning_group.name})
        elif self._location:
            return ('location', {'id': self._location.location_id,
                                 'name': self._location.display_name})
        return ('user', self._user_meta(self.owner_id))

    @property
    def _creating_user(self):
        try:
            creator_id = self.raw_data['opened_by']
        except KeyError:
            creator_id = None
            if 'actions' in self.raw_data:
                for action in self.raw_data['actions']:
                    if action['action_type'] == 'create':
                        action_doc = CommCareCaseAction.wrap(action)
                        creator_id = action_doc.get_user_id()
                        break

        if not creator_id:
            return None
        return self._user_meta(creator_id)

    def _user_meta(self, user_id):
        return {'id': user_id, 'name': self._get_username(user_id)}

    def _user_not_found_display(self, user_id):
        return _("Unknown [%s]") % user_id

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
