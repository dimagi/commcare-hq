from corehq.apps.reports.filters.base import (
    BaseMultipleOptionFilter, BaseSingleOptionFilter)

from .constants import get_user_data_set


class BlockFilter(BaseMultipleOptionFilter):
    slug = "blocks"
    label = "Block"
    default_text = "All"
    
    @property
    def options(self):
        return [(block, block) for block in get_user_data_set()['blocks']]


class AWCFilter(BaseMultipleOptionFilter):
    slug = "awcs"
    label = "AWC"
    default_text = "All"
    
    @property
    def options(self):
        return [(awc, awc) for awc in get_user_data_set()['awcs']]

class SelectBlockFilter(BaseSingleOptionFilter):
    slug = "block"
    label = "Block"
    default_text = None

    @property
    def options(self):
        return [('Atri', 'Atri'), ('Wazirganj', 'Wazirganj')]


class GramPanchayatFilter(BaseSingleOptionFilter):
    slug = 'gp'
    label = "Gram Panchayat"
    default_text = None

    @property
    def options(self):
        return [(awc, awc) for awc in get_user_data_set()['gp']]

