from django.utils.translation import ugettext_lazy as _

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from custom.inddex.sqldata import FoodCodeData, FoodBaseTermData
from corehq.apps.reports.filters.dates import DatespanFilter


class DateRangeFilter(DatespanFilter):
    label = _('Date Range')


class AgeRangeFilter(BaseSingleOptionFilter):
    slug = 'age_range'
    label = _('Age range')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('0-5.9 months', _('0-5.9 months')),
            ('06-59 months', _('06-59 months')),
            ('5-6 years', _('5-6 years')),
            ('7-10 years', _('7-10 years')),
            ('11-14 years', _('11-14 years')),
            ('15-49 years', _('15-49 years')),
            ('50-64 years', _('50-64 years')),
            ('65+ years', _('65+ years'))
        ]


class GenderFilter(BaseSingleOptionFilter):
    slug = 'gender'
    label = _('Gender')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('male', _('Male')),
            ('female', _('Female'))
        ]


class PregnancyFilter(BaseSingleOptionFilter):
    slug = 'pregnant'
    label = _('Pregnancy')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('yes', _('Yes')),
            ('no', _('No')),
            ('refuse_to_answer', _('Refuse to answer')),
            ('dont_know', _('Don\'t know'))
        ]


class SettlementAreaFilter(BaseSingleOptionFilter):
    slug = 'urban_rural'
    label = _('Urban/Rural')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('urban', _('Urban')),
            ('rural', _('Rural'))
        ]


class BreastFeedingFilter(BaseSingleOptionFilter):
    slug = 'breastfeeding'
    label = _('Breastfeeding')
    default_text = _('All')

    @property
    def options(self):
        # TODO: Check value in production application ?? refuse_de_rpondre
        return [
            ('yes', _('Yes')),
            ('no', _('No')),
            ('refuse_de_rpondre', _('Refuse to answer'))
        ]


class SupplementsFilter(BaseSingleOptionFilter):
    slug = 'supplements'
    label = _('Supplement Use')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('yes', _('Yes')),
            ('no', _('No'))
        ]


class RecallStatusFilter(BaseSingleOptionFilter):
    slug = 'recall_status'
    label = _('Recall Status')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('Open', _('Not Completed')),
            ('Completed', _('Completed'))
        ]


class GapDescriptionFilter(BaseSingleOptionFilter):
    slug = 'gap_description'
    label = _('Gap description')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('conv factor available', 'conv factor available'),
            ('fct data available', 'fct data available'),
            ('no conversion factor available', 'no conversion factor available'),
            ('no fct data available', 'no fct data available'),
            ('not applicable', 'not applicable'),
            (
                'using conversion factor from the reference food code',
                'using conversion factor from the reference food code'
            ),
            ('using fct data from the reference food code', 'using fct data from the reference food code'),
        ]


class GapTypeFilter(BaseSingleOptionFilter):
    slug = 'gap_type'
    label = _('Gap type')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('fct', 'fct'),
            ('conversion factor', 'conversion factor'),
        ]


class FoodCodeFilter(BaseSingleOptionFilter):
    slug = 'food_code'
    label = _('Food Code')
    default_text = _('All')

    @property
    def food_codes(self):
        return FoodCodeData(config={'domain': self.domain}).rows

    @property
    def options(self):
        return [
            (str(x), str(x)) for x in self.food_codes
        ]


class FoodBaseTermFilter(BaseSingleOptionFilter):
    slug = 'food_base_term'
    label = _('Food base term')
    default_text = _('All')

    @property
    def food_base_terms(self):
        return FoodBaseTermData(config={'domain': self.domain}).rows

    @property
    def options(self):
        return [
            (x, x) for x in self.food_base_terms
        ]


class FoodTypeFilter(BaseSingleOptionFilter):
    slug = 'food_type'
    label = _('Food type')
    default_text = _('All')

    @property
    def options(self):
        return [
            (x, x) for x in ['food_item', 'non_std_food_item', 'non_std_recipe', 'std_recipe']
        ]
