from django.utils.translation import ugettext_lazy as _

from sqlagg.columns import SimpleColumn

from corehq.apps.reports.datatables import DataTablesColumn
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.sqlreport import DatabaseColumn, SqlData
from corehq.apps.userreports.util import get_table_name
from custom.inddex.const import (
    AGE_RANGES,
    FOOD_CONSUMPTION,
    ConvFactorGaps,
    FctGaps,
)


class DateRangeFilter(DatespanFilter):
    label = _('Date Range')


class AgeRangeFilter(BaseSingleOptionFilter):
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
    slug = 'gap'
    label = _('Gap description')
    default_text = _('All')

    @property
    def options(self):
        return [
            (f'{klass.slug}-{code}', klass.get_description(code))
            for klass, code in [
                # This is the order the partner asked for
                (ConvFactorGaps, ConvFactorGaps.AVAILABLE),
                (FctGaps, FctGaps.AVAILABLE),
                (ConvFactorGaps, ConvFactorGaps.BASE_TERM),
                (FctGaps, FctGaps.BASE_TERM),
                (FctGaps, FctGaps.REFERENCE),
                (FctGaps, FctGaps.INGREDIENT_GAPS),
                (ConvFactorGaps, ConvFactorGaps.NOT_AVAILABLE),
                (FctGaps, FctGaps.NOT_AVAILABLE),
            ]
        ]


class GapTypeFilter(BaseSingleOptionFilter):
    slug = 'gap_type'
    label = _('Gap type')
    default_text = _('All')

    @property
    def options(self):
        return [
            (ConvFactorGaps.slug, ConvFactorGaps.name),
            (FctGaps.slug, FctGaps.name),
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


class CaseOwnerData(SqlData):
    engine_id = 'ucr'
    filters = []
    group_by = ['owner_name']
    headers = [DataTablesColumn('Case owner')]
    columns = [DatabaseColumn('Case owner', SimpleColumn('owner_name'))]

    @property
    def table_name(self):
        return get_table_name(self.config['domain'], FOOD_CONSUMPTION)


class CaseOwnersFilter(BaseSingleOptionFilter):
    slug = 'owner_name'
    label = _('Case Owners')
    default_text = _('All')

    @property
    def options(self):
        owner_data = CaseOwnerData(config={'domain': self.domain})
        names = {
            owner['owner_name']
            for owner in owner_data.get_data()
            if owner.get('owner_name')
        }
        return [(x, x) for x in names]


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
