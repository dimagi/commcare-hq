from django.utils.translation import ugettext_lazy as _

from corehq.apps.reports.filters.base import (
    BaseDrilldownOptionFilter,
    BaseSingleOptionFilter,
    BaseMultipleOptionFilter,
)
from corehq.apps.reports.filters.dates import DatespanFilter
from custom.inddex.const import AGE_RANGES, ConvFactorGaps, FctGaps


class DateRangeFilter(DatespanFilter):
    label = _('Date Range')


class AgeRangeFilter(BaseMultipleOptionFilter):
    slug = 'age_range'
    label = _('Age Range')
    default_text = _('All')

    @property
    def options(self):
        return [(age_range.slug, age_range.name) for age_range in AGE_RANGES]


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


class SettlementAreaFilter(BaseMultipleOptionFilter):
    slug = 'urban_rural'
    label = _('Urban/Rural')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('peri-urban', _('Peri-urban')),
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


class GapDescriptionFilter(BaseDrilldownOptionFilter):
    slug = 'gap'
    label = _('Gap Description')
    default_text = _('All')

    @classmethod
    def get_labels(cls):
        return [
            # will come through as `gap_type` and `gap_code`
            ("Gap Type", "All", 'type'),
            ("Gap Description", "All", 'code'),
        ]

    @property
    def drilldown_map(self):
        return [
            {
                'text': klass.name,
                'val': klass.slug,
                'next': [
                    {
                        'text': klass.DESCRIPTIONS[code],
                        'val': str(code),
                        'next': [],
                    }
                    for code in klass.DESCRIPTIONS
                ]
            }
            for klass in [ConvFactorGaps, FctGaps]
        ]


class GapTypeFilter(BaseSingleOptionFilter):
    slug = 'gap_type'
    label = _('Gap Type')
    default_text = _('All')

    @property
    def options(self):
        return [
            (ConvFactorGaps.slug, ConvFactorGaps.name),
            (FctGaps.slug, FctGaps.name),
        ]


class FoodTypeFilter(BaseMultipleOptionFilter):
    slug = 'food_type'
    label = _('Food Type')
    default_text = _('All')

    @property
    def options(self):
        return [
            (x, x) for x in ['food_item', 'non_std_food_item', 'std_recipe', 'non_std_recipe']
        ]


class FaoWhoGiftFoodGroupDescriptionFilter(BaseMultipleOptionFilter):
    slug = 'fao_who_gift_food_group_code'
    label = _('FAO/WHO GIFT Food Group Description')
    default_text = _('All')

    @property
    def options(self):
        return [
            ('1', 'Cereals and their products (1)'),
            ('2', 'Roots, tubers, plantains and their products (2)'),
            ('3', 'Pulses, seeds and nuts and their products (3)'),
            ('4', 'Milk and milk products (4)'),
            ('5', 'Eggs and their products (5)'),
            ('6', 'Fish, shellfish and their products (6)'),
            ('7', 'Meat and meat products (7)'),
            ('8', 'Insects, grubs and their products (8)'),
            ('9', 'Vegetables and their products (9)'),
            ('10', 'Fruits and their products (10)'),
            ('11', 'Fats and oils (11)'),
            ('12', 'Sweets and sugars (12)'),
            ('13', 'Spices and condiments (13)'),
            ('14', 'Beverages (14)'),
            ('15', 'Foods for particular nutritional uses (15)'),
            ('16', 'Food supplements and similar (16)'),
            ('17', 'Food additives (17)'),
            ('18', 'Composite foods (18)'),
            ('19', 'Savoury snacks (19)'),
        ]
