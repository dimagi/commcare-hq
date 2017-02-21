import datetime
import dateutil
from django.core import cache
from django.core.urlresolvers import NoReverseMatch
from django.template.defaultfilters import yesno
from django.utils import html
from django.utils.translation import ugettext as _
import json
from casexml.apps.case.models import CommCareCaseAction
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CouchUser
from corehq.util.dates import iso_string_to_datetime
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.decorators.memoized import memoized


class CaseInfo(object):

    def __init__(self, report, case):
        """
        case is a dict object of the case doc
        """
        self.case = case
        self.report = report

    @property
    def case_type(self):
        return self.case['type']

    @property
    def case_name(self):
        return self.case['name']

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
            return absolute_reverse('case_details', args=[self.report.domain, self.case_id])
        except NoReverseMatch:
            return None

    @property
    def is_closed(self):
        return self.case['closed']

    def _dateprop(self, prop, iso=True):
        val = self.report.date_to_json(self.parse_date(self.case[prop]))
        if iso:
            val = 'T'.join(val.split(' ')) if val else None
        return val

    @property
    def opened_on(self):
        return self._dateprop('opened_on')

    @property
    def modified_on(self):
        return self._dateprop('modified_on')

    @property
    def closed_on(self):
        return self._dateprop('closed_on')

    @property
    def creating_user(self):
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
    @memoized
    def location(self):
        try:
            return SQLLocation.objects.get(location_id=self.owner_id)
        except SQLLocation.DoesNotExist:
            return None

    @property
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
        return self.report.individual or self.owner_id

    @property
    def owner_id(self):
        if 'owner_id' in self.case:
            return self.case['owner_id']
        elif 'user_id' in self.case:
            return self.case['user_id']
        else:
            return ''

    @property
    @memoized
    def owning_group(self):
        mc = cache.caches['default']
        cache_key = "%s.%s" % (Group.__class__.__name__, self.owner_id)
        try:
            if mc.has_key(cache_key):
                cached_obj = json.loads(mc.get(cache_key))
                wrapped = Group.wrap(cached_obj)
                return wrapped
            else:
                group_obj = Group.get(self.owner_id)
                mc.set(cache_key, json.dumps(group_obj.to_json()))
                return group_obj
        except Exception:
            return None

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
        except:
            try:
                date_obj = dateutil.parser.parse(date_string)
                if isinstance(date_obj, datetime.datetime):
                    return date_obj.replace(tzinfo=None)
                else:
                    return date_obj
            except:
                return date_string


class CaseDisplay(CaseInfo):

    @property
    def closed_display(self):
        return yesno(self.is_closed, "closed,open")

    @property
    def case_link(self):
        url = self.case_detail_url
        if url:
            return html.mark_safe("<a class='ajax_dialog' href='%s' target='_blank'>%s</a>" % (
                self.case_detail_url, html.escape(self.case_name_display)))
        else:
            return "%s (bad ID format)" % self.case_name

    @property
    def opened_on(self):
        return self._dateprop('opened_on', False)

    @property
    def modified_on(self):
        return self._dateprop('modified_on', False)

    @property
    def owner_display(self):
        owner_type, owner = self.owner
        if owner_type == 'group':
            return '<span class="label label-default">%s</span>' % owner['name']
        else:
            return owner['name']

    def user_not_found_display(self, user_id):
        return _("Unknown [%s]") % user_id

    @property
    def creating_user(self):
        user = super(CaseDisplay, self).creating_user
        if user is None:
            return _("No data")
        else:
            return user['name'] or self.user_not_found_display(user['id'])
