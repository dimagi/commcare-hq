from django.utils.translation import ugettext_lazy as _

from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from custom.inddex.sqldata import FiltersData
from corehq.apps.reports.filters.dates import DatespanFilter


class DateRangeFilter(DatespanFilter):
    label = _('Date Range')


class AgeRangeFilter(BaseSingleOptionFilter):
    slug = 'age_range'
    label = _('Age Range')
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
        ]


class SettlementAreaFilter(BaseSingleOptionFilter):
    slug = 'urban_rural'
    label = _('Urban/Rural')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('per-urban', _('Peri-urban')),
            ('urban', _('Urban')),
            ('rural', _('Rural'))
        ]


class BreastFeedingFilter(BaseSingleOptionFilter):
    slug = 'breastfeeding'
    label = _('Breastfeeding')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('yes', _('Yes')),
            ('no', _('No')),
        ]


class SupplementsFilter(BaseSingleOptionFilter):
    slug = 'supplements'
    label = _('Supplement Use')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('yes', _('Yes')),
            ('no', _('Not'))
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


class FoodTypeFilter(BaseSingleOptionFilter):
    slug = 'food_type'
    label = _('Food type')
    default_text = _('All')

    @property
    def options(self):
        return [
            (x, x) for x in ['food_item', 'non_std_food_item', 'std_recipe', 'non_std_recipe']
        ]


class CaseOwnersFilter(BaseSingleOptionFilter):
    slug = 'case_owners'
    label = _('Case Owners')
    default_text = _('All')

    @property
    def options(self):
        return [
            (x, x) for x in FiltersData(config={'domain': self.domain}).rows[0]
        ]


class FaoWhoGiftFoodGroupDescriptionFilter(BaseSingleOptionFilter):
    slug = 'fao_who_gift_food_group_description'
    label = _('FAO/WHO GIFT Food Group Description')
    default_text = _('All')

    @property
    def options(self):
        return [
            (x, x) for x in [
                'Cereals and their products (1)', 'Roots, tubers, plantains and their products (2)',
                'Pulses, seeds and nuts and their products (3)', 'Milk and milk products (4)',
                'Eggs and their products (5)', 'Fish, shellfish and their products (6)',
                'Meat and meat products (7)', 'Insects, grubs and their products (8)',
                'Vegetables and their products( 9)', 'Fruits and their products (10)',
                'Fats and oils (11)', 'Sweets and sugars (12)', 'Spices and condiments (13)', 'Beverages (14)',
                'Foods for particular nutritional uses (15)', 'Food supplements and similar (16)',
                'Food additives (17)', 'Composite foods (18)', 'Savoury snacks (19)',
            ]
        ]
