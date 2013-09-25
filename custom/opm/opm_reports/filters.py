from corehq.apps.reports.filters.base import BaseMultipleOptionFilter


class BlockFilter(BaseMultipleOptionFilter):
    slug = "block"
    label = "Block"
    default_text = "All"
    
    @property
    def options(self):
        return [
            ('ninth', "9th St"),
            ('eighth', "8th St"),
        ]

class AWCFilter(BaseMultipleOptionFilter):
    slug = "awc"
    label = "AWC"
    default_text = "All"
    
    @property
    def options(self):
        return [
            ('ninth', "9th St"),
            ('eighth', "8th St"),
        ]