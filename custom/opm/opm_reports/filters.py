# from dimagi.utils.decorators.memoized import memoized

from corehq.apps.users.models import CommCareUser
from corehq.apps.reports.filters.base import (
    BaseMultipleOptionFilter, BaseSingleOptionFilter, CheckboxFilter)

from .constants import *


class UserDataMixin(object):
    _user_data = None

    @property
    def user_data(self):
        if self._user_data is None:
            from corehq.apps.es.users import UserES
            # import ipdb; ipdb.set_trace()
            users = CommCareUser.by_domain(DOMAIN)
            self._user_data = {
                'blocks': sorted(list(set(u.user_data.get('block') for u in users))),
                'awcs': sorted(list(set(u.user_data.get('awc') for u in users))),
                'gp': sorted(list(set(u.user_data.get('gp') for u in users))),
            }
        return self._user_data


class BlockFilter(UserDataMixin, BaseMultipleOptionFilter):
    slug = "blocks"
    label = "Block"
    default_text = "All"

    @property
    def options(self):
        return [(block, block) for block in self.user_data['blocks']]


class AWCFilter(UserDataMixin, BaseMultipleOptionFilter):
    slug = "awcs"
    label = "AWC"
    default_text = "All"

    @property
    def options(self):
        return [(awc, awc) for awc in self.user_data['awcs']]

class SelectBlockFilter(BaseSingleOptionFilter):
    slug = "block"
    label = "Block"
    default_text = None

    @property
    def options(self):
        return [('Atri', 'Atri'), ('Wazirganj', 'Wazirganj')]


class GramPanchayatFilter(UserDataMixin, BaseSingleOptionFilter):
    slug = 'gp'
    label = "Gram Panchayat"
    default_text = None

    @property
    def options(self):
        return [(awc, awc) for awc in self.user_data['gp']]


class SnapshotFilter(CheckboxFilter):
    label = 'Load from snapshot'
    slug = 'load_snapshot'

    @property
    def filter_context(self):
        first_load = self.request.GET.get('hq_filters', False)
        if first_load:
            return {'checked': True}
        else:
            return {'checked': self.request.GET.get(self.slug, False)}

